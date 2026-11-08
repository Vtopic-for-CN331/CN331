from datetime import timedelta
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from . import selectors, services
from .forms import EditTopicForm, TopicForm
from .models import Comment, Side, Topic


class TopicModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="modeluser", password="password123"
        )
        self.topic = Topic.objects.create(
            title="Test Topic",
            description="Test Description",
            created_by=self.user,
        )

    def test_topic_str(self):
        """ทดสอบ String Representation ของ Topic"""
        self.assertEqual(str(self.topic), "Test Topic")

    def test_topic_expiration(self):
        """ทดสอบสถานะหมดเวลาของ Topic"""
        self.assertFalse(self.topic.is_expired())

        self.topic.end_date = timezone.now() - timedelta(days=1)
        self.topic.save()
        self.assertTrue(self.topic.is_expired())


class SideAndCommentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="subuser", password="password123"
        )
        self.topic = Topic.objects.create(
            title="Sample Topic",
            description="Desc",
            created_by=self.user,
        )
        self.side = Side.objects.create(topic=self.topic, name="Agree")
        self.comment = Comment.objects.create(
            topic=self.topic,
            side=self.side,
            author=self.user,
            text="Great topic!",
        )

    def test_side_str(self):
        """ทดสอบ String Representation ของ Side"""
        self.assertEqual(str(self.side), "Sample Topic - Agree")

    def test_comment_str(self):
        """ทดสอบ String Representation ของ Comment"""
        self.assertTrue(str(self.comment))


class DebatesFormTest(TestCase):
    def test_topic_form_valid_and_invalid(self):
        """ทดสอบ Form การสร้างกระทู้"""
        valid_form = TopicForm(
            data={
                "title": "Django vs FastAPI",
                "description": "Which is better?",
                "is_anonymous": False,
                "tags_string": "python, backend",
            }
        )
        self.assertTrue(valid_form.is_valid())

        invalid_form = TopicForm(data={"title": "", "description": "No title"})
        self.assertFalse(invalid_form.is_valid())

    def test_edit_topic_form(self):
        """ทดสอบ Form การแก้ไขกระทู้"""
        form = EditTopicForm(
            data={
                "title": "Updated Title",
                "description": "Updated Desc",
                "is_anonymous": False,
            }
        )
        self.assertTrue(form.is_valid())


class DebatesServiceAndSelectorTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="user1", password="password123"
        )
        self.user2 = User.objects.create_user(
            username="user2", password="password123"
        )

    def test_create_topic_with_sides_service(self):
        """ทดสอบ Service การสร้าง Topic พร้อม Sides และ Tags"""
        form = TopicForm(
            data={
                "title": "Cats vs Dogs",
                "description": "Which pet is better?",
                "is_anonymous": True,
                "tags_string": "pets, animals",
            }
        )
        self.assertTrue(form.is_valid())

        topic = services.create_topic_with_sides(
            self.user1, form, ["Cats", "Dogs"]
        )
        self.assertEqual(topic.title, "Cats vs Dogs")
        self.assertEqual(topic.sides.count(), 2)
        self.assertEqual(topic.tags.count(), 2)

    def test_create_topic_with_insufficient_sides(self):
        """ทดสอบการสร้างหัวข้อที่มีตัวเลือกไม่ถึง 2 ฝั่ง"""
        form = TopicForm(data={"title": "Single Side", "description": "Desc"})
        self.assertTrue(form.is_valid())
        with self.assertRaises(ValidationError):
            services.create_topic_with_sides(
                self.user1, form, ["Only One Side"]
            )

    def test_submit_vote_and_validation(self):
        """ทดสอบการโหวตและข้อผิดพลาดห้ามโหวตซ้ำ"""
        topic = Topic.objects.create(
            title="Vote Test",
            description="Desc",
            created_by=self.user1,
        )
        side1 = Side.objects.create(topic=topic, name="Yes")
        side2 = Side.objects.create(topic=topic, name="No")

        # โหวตสำเร็จ
        services.submit_vote(
            user=self.user2,
            topic=topic,
            side_id=side1.id,
            comment_text="I agree",
        )
        self.assertEqual(topic.comments.count(), 1)

        # โหวตซ้ำคนเดิม
        with self.assertRaises(ValidationError):
            services.submit_vote(
                user=self.user2,
                topic=topic,
                side_id=side2.id,
                comment_text="Change",
            )

        # ไม่เลือกฝั่ง
        with self.assertRaises(ValidationError):
            services.submit_vote(
                user=self.user1,
                topic=topic,
                side_id="",
                comment_text="No side",
            )

    def test_expired_topic_voting_validation(self):
        """ทดสอบการห้ามโหวตหัวข้อที่หมดเวลา"""
        topic = Topic.objects.create(
            title="Expired Topic",
            description="Desc",
            created_by=self.user1,
            end_date=timezone.now() - timedelta(hours=1),
        )
        side = Side.objects.create(topic=topic, name="A")
        with self.assertRaises(ValidationError):
            services.submit_vote(
                user=self.user2,
                topic=topic,
                side_id=side.id,
                comment_text="Late",
            )

    def test_update_and_close_and_delete_topic_services(self):
        """ทดสอบ Service แก้ไข ปิดโหวต และลบกระทู้"""
        topic = Topic.objects.create(
            title="Orig Title",
            description="Orig Desc",
            created_by=self.user1,
        )
        form = EditTopicForm(
            data={"title": "New Title", "description": "New Desc"},
            instance=topic,
        )
        self.assertTrue(form.is_valid())

        # Update
        updated = services.update_topic(topic, form)
        self.assertEqual(updated.title, "New Title")

        # Close voting
        services.close_topic_voting(self.user1, topic)
        topic.refresh_from_db()
        self.assertTrue(topic.is_expired())

        # Close voting unauthorized
        with self.assertRaises(PermissionDenied):
            services.close_topic_voting(self.user2, topic)

        # Delete by unauthorized user
        with self.assertRaises(PermissionDenied):
            services.delete_topic_by_user(self.user2, topic)

        # Delete by owner
        services.delete_topic_by_user(self.user1, topic)
        self.assertEqual(Topic.objects.count(), 0)

    def test_selectors_queries(self):
        """ทดสอบ Selectors ทั้งหมด"""
        t1 = Topic.objects.create(
            title="Python Guide",
            description="Desc",
            created_by=self.user1,
        )
        Topic.objects.create(
            title="Web CSS",
            description="Desc",
            created_by=self.user1,
        )
        side = Side.objects.create(topic=t1, name="Agree")
        Comment.objects.create(
            topic=t1, side=side, author=self.user2, text="Nice"
        )

        # Search & user queries
        self.assertIn(t1, selectors.get_topics(search_query="Python"))
        self.assertEqual(selectors.get_user_topics(self.user1).count(), 2)
        self.assertEqual(selectors.get_user_comments(self.user2).count(), 1)
        self.assertIsNotNone(selectors.get_user_vote(self.user2, t1))
        self.assertIsNone(selectors.get_user_vote(self.user1, t1))


class DebatesViewClientTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="viewuser", password="password123"
        )
        self.other_user = User.objects.create_user(
            username="otheruser", password="password123"
        )
        self.client = Client()
        self.topic = Topic.objects.create(
            title="View Topic",
            description="Desc",
            created_by=self.user,
        )
        self.side = Side.objects.create(topic=self.topic, name="Option 1")

    def test_topic_list_views(self):
        """ทดสอบหน้า Topic List ทั้งแบบค้นหา และแสดงกระทู้ที่หมดอายุ"""
        res = self.client.get(
            reverse("topic_list"), {"q": "View", "show_all": "true"}
        )
        self.assertEqual(res.status_code, 200)

    def test_topic_detail_post_voting_and_filtering(self):
        """ทดสอบหน้า Detail การส่งโหวต และการกรองคอมเมนต์"""
        post_url = reverse("topic_detail", args=[self.topic.id])
        res = self.client.post(
            post_url, {"side": self.side.id, "comment_text": "Guest vote"}
        )
        self.assertNotEqual(res.status_code, 200)

        self.client.login(username="viewuser", password="password123")
        res = self.client.post(
            post_url, {"side": self.side.id, "comment_text": "Valid vote"}
        )
        self.assertRedirects(res, post_url)

        res = self.client.get(post_url, {"side_filter": str(self.side.id)})
        self.assertEqual(res.status_code, 200)

    def test_create_topic_view_post(self):
        """ทดสอบการสร้างหัวข้อผ่าน View POST"""
        self.client.login(username="viewuser", password="password123")
        res = self.client.post(
            reverse("create_topic"),
            {
                "title": "New Web Topic",
                "description": "Description",
                "is_anonymous": False,
                "sides": ["Side 1", "Side 2"],
                "tags_string": "web, test",
            },
        )
        self.assertRedirects(res, reverse("topic_list"))

        topic = Topic.objects.get(title="New Web Topic")
        self.assertSetEqual(
            set(topic.tags.values_list("name", flat=True)), {"web", "test"}
        )

        list_response = self.client.get(reverse("topic_list"))
        self.assertContains(list_response, "web")
        self.assertContains(list_response, "test")

        detail_response = self.client.get(
            reverse("topic_detail", args=[topic.id])
        )
        self.assertContains(detail_response, "web")
        self.assertContains(detail_response, "test")

    def test_edit_topic_view_actions(self):
        """ทดสอบหน้าแก้ไขหัวข้อและการกดปิดโหวต"""
        self.client.login(username="viewuser", password="password123")
        edit_url = reverse("edit_topic", args=[self.topic.id])

        # ปิดโหวตผ่าน action
        res = self.client.post(edit_url, {"action": "close_voting"})
        self.assertRedirects(
            res, reverse("topic_detail", args=[self.topic.id])
        )

        # แก้ไขข้อมูลปกติ
        res = self.client.post(
            edit_url, {"title": "Edited Title", "description": "Edited Desc"}
        )
        self.assertRedirects(
            res, reverse("topic_detail", args=[self.topic.id])
        )

    def test_user_profile_view(self):
        """ทดสอบหน้าดูโปรไฟล์ส่วนตัว"""
        self.client.login(username="viewuser", password="password123")
        res = self.client.get(reverse("user_profile"))
        self.assertEqual(res.status_code, 200)

    def test_delete_topic_view(self):
        """ทดสอบการลบกระทู้"""
        self.client.login(username="viewuser", password="password123")  # nosec B106
        res = self.client.post(reverse("delete_topic", args=[self.topic.id]))
        self.assertRedirects(res, reverse("topic_list"))

    def test_signup_view_post_invalid(self):
        """ทดสอบการส่งฟอร์มสมัครสมาชิกแบบข้อมูลไม่ถูกต้อง"""
        res = self.client.post(
            reverse("signup"), {"username": "", "password": "123"}  # nosec B105
        )
        self.assertEqual(res.status_code, 200)

    def test_topic_list_search_and_filter(self):
        """ทดสอบการค้นหาและการกรองกระทู้ที่หมดอายุและยังไม่หมดอายุ"""
        Topic.objects.create(
            title="Old Expired Topic",
            description="Old Description",
            created_by=self.user,
            end_date=timezone.now() - timedelta(days=5),
        )
        res_all = self.client.get(reverse("topic_list"), {"show_all": "true"})
        self.assertEqual(res_all.status_code, 200)

        res_active = self.client.get(
            reverse("topic_list"), {"show_all": "false"}
        )
        self.assertEqual(res_active.status_code, 200)
