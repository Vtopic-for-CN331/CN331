from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from . import services
from .models import Comment, Side, Topic


class DebateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.other_user = User.objects.create_user(username="otheruser", password="password123")
        self.topic = Topic.objects.create(
            title="หัวข้อทดสอบระบบ",
            description="รายละเอียดทดสอบ",
            created_by=self.user,
            end_date=timezone.now() + timedelta(days=1),
        )
        self.side = Side.objects.create(topic=self.topic, name="เห็นด้วย")
        self.other_side = Side.objects.create(topic=self.topic, name="ไม่เห็นด้วย")

    def create_topic_form(self, title="หัวข้อใหม่"):
        from .forms import TopicForm

        return TopicForm({"title": title, "description": "รายละเอียดหัวข้อ", "end_date": ""})

    def test_topic_is_expired(self):
        self.topic.end_date = timezone.now() - timedelta(days=1)
        self.topic.save()
        self.assertTrue(self.topic.is_expired())

    def test_topic_list_hides_expired_topics_in_search_and_default_listing(self):
        expired = Topic.objects.create(
            title="หัวข้อหมดอายุ",
            description="ค้นหาคำนี้ได้",
            created_by=self.user,
            end_date=timezone.now() - timedelta(seconds=1),
        )

        response = self.client.get(reverse("topic_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, expired.title)
        self.assertContains(response, self.topic.title)

        search_response = self.client.get(reverse("topic_list"), {"q": "คำนี้ได้"})
        self.assertNotContains(search_response, expired.title)

    def test_topic_list_displays_post_date_and_time(self):
        posted_at = datetime(2026, 11, 5, 14, 30, tzinfo=ZoneInfo("Asia/Bangkok"))
        Topic.objects.filter(id=self.topic.id).update(created_at=posted_at)

        response = self.client.get(reverse("topic_list"))

        self.assertContains(response, "โพสต์เมื่อ 05/11/2026 14:30")

    def test_topic_detail_displays_post_date_and_time(self):
        posted_at = datetime(2026, 11, 5, 14, 30, tzinfo=ZoneInfo("Asia/Bangkok"))
        Topic.objects.filter(id=self.topic.id).update(created_at=posted_at)

        response = self.client.get(reverse("topic_detail", args=[self.topic.id]))

        self.assertContains(response, "โพสต์เมื่อ 05/11/2026 14:30")

    def test_topic_list_is_newest_first_and_paginated(self):
        older = self.topic
        for index in range(10):
            Topic.objects.create(
                title=f"หัวข้อ {index}", description="รายละเอียด", created_by=self.user
            )

        first_page = self.client.get(reverse("topic_list"))
        second_page = self.client.get(reverse("topic_list"), {"page": 2})
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(first_page.context["page_obj"].paginator.num_pages, 2)
        self.assertNotContains(first_page, older.title)
        self.assertContains(second_page, older.title)

    def test_topic_list_keeps_search_query_in_pagination_links(self):
        for index in range(11):
            Topic.objects.create(
                title=f"ค้นหา {index}", description="คำค้น", created_by=self.user
            )
        response = self.client.get(reverse("topic_list"), {"q": "ค้นหา"})
        self.assertIn("q=%E0%B8%84%E0%B9%89%E0%B8%99%E0%B8%AB%E0%B8%B2&page=2", response.content.decode())

    def test_create_topic_redirects_if_not_logged_in(self):
        response = self.client.get(reverse("create_topic"))
        self.assertEqual(response.status_code, 302)

    def test_create_topic_requires_two_distinct_sides(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("create_topic"),
            {"title": "หัวข้อใหม่", "description": "รายละเอียด", "sides": ["เห็นด้วย"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "อย่างน้อย 2 ฝั่ง")
        self.assertFalse(Topic.objects.filter(title="หัวข้อใหม่").exists())

    def test_create_topic_rejects_duplicate_side_names_case_insensitively(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("create_topic"),
            {
                "title": "หัวข้อใหม่",
                "description": "รายละเอียด",
                "sides": ["เห็นด้วย", " เห็นด้วย "],
            },
        )
        self.assertContains(response, "ชื่อตัวเลือกต้องไม่ซ้ำกัน")
        self.assertFalse(Topic.objects.filter(title="หัวข้อใหม่").exists())

    def test_create_topic_rejects_side_names_over_model_limit(self):
        with self.assertRaises(ValidationError):
            services.validate_side_names(["x" * 101, "other"])

    def test_create_topic_trims_side_names(self):
        form = self.create_topic_form()
        self.assertTrue(form.is_valid())
        topic = services.create_topic_with_sides(self.user, form, ["  ใช่  ", "  ไม่ใช่ "])
        self.assertEqual(list(topic.sides.order_by("id").values_list("name", flat=True)), ["ใช่", "ไม่ใช่"])

    def test_submit_vote_success(self):
        services.submit_vote(self.user, self.topic, self.side.id, "เหตุผลที่เห็นด้วย")
        comment = Comment.objects.get(topic=self.topic, author=self.user)
        self.assertEqual(comment.side, self.side)
        self.assertEqual(comment.text, "เหตุผลที่เห็นด้วย")

    def test_submit_vote_rejects_duplicate_vote(self):
        services.submit_vote(self.user, self.topic, self.side.id, "เหตุผลแรก")
        with self.assertRaises(ValidationError):
            services.submit_vote(self.user, self.topic, self.other_side.id, "เหตุผลที่สอง")
        self.assertEqual(Comment.objects.filter(topic=self.topic, author=self.user).count(), 1)

    def test_database_constraint_prevents_duplicate_votes(self):
        Comment.objects.create(topic=self.topic, author=self.user, side=self.side, text="ครั้งแรก")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Comment.objects.create(
                    topic=self.topic, author=self.user, side=self.other_side, text="ครั้งที่สอง"
                )

    def test_submit_vote_rejects_side_from_another_topic(self):
        another_topic = Topic.objects.create(
            title="อีกหัวข้อ", description="รายละเอียด", created_by=self.user
        )
        another_side = Side.objects.create(topic=another_topic, name="เลือก")
        with self.assertRaises(ValidationError):
            services.submit_vote(self.user, self.topic, another_side.id, "เหตุผล")

    def test_submit_vote_rejects_missing_comment_or_side(self):
        with self.assertRaises(ValidationError):
            services.submit_vote(self.user, self.topic, self.side.id, "  ")
        with self.assertRaises(ValidationError):
            services.submit_vote(self.user, self.topic, None, "เหตุผล")

    def test_submit_vote_rejects_expired_topic(self):
        self.topic.end_date = timezone.now() - timedelta(seconds=1)
        self.topic.save()
        with self.assertRaises(ValidationError):
            services.submit_vote(self.user, self.topic, self.side.id, "เหตุผล")

    def test_topic_detail_shows_per_side_vote_results(self):
        services.submit_vote(self.user, self.topic, self.side.id, "เหตุผล")
        Comment.objects.create(
            topic=self.topic, author=self.other_user, side=None, text="ความเห็นที่ไม่ใช่โหวต"
        )
        response = self.client.get(reverse("topic_detail", args=[self.topic.id]))
        self.assertContains(response, "1 โหวต")
        self.assertContains(response, "เห็นด้วย")
        self.assertContains(response, "ผู้เข้าร่วมทั้งหมด 1 คน")

    def test_topic_edit_is_allowed_for_owner(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("edit_topic", args=[self.topic.id]),
            {"title": "แก้ไขแล้ว", "description": "รายละเอียดใหม่"},
        )
        self.assertRedirects(response, reverse("topic_detail", args=[self.topic.id]))
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.title, "แก้ไขแล้ว")

    def test_topic_edit_is_denied_for_non_owner(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse("edit_topic", args=[self.topic.id]))
        self.assertEqual(response.status_code, 403)

    def test_topic_delete_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("delete_topic", args=[self.topic.id]))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Topic.objects.filter(id=self.topic.id).exists())

    def test_topic_delete_is_allowed_for_owner(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("delete_topic", args=[self.topic.id]))
        self.assertRedirects(response, reverse("topic_list"))
        self.assertFalse(Topic.objects.filter(id=self.topic.id).exists())

    def test_topic_delete_is_denied_for_non_owner(self):
        self.client.force_login(self.other_user)
        response = self.client.post(reverse("delete_topic", args=[self.topic.id]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Topic.objects.filter(id=self.topic.id).exists())
