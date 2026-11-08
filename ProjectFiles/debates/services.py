from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Comment, Side, Tag, Topic


@transaction.atomic
def create_topic_with_sides(user, form, side_names):
    """สร้างกระทู้พร้อมตัวเลือกฝั่งและ Tag ภายใต้ Transaction เดียวกัน"""
    cleaned_sides = [name.strip() for name in side_names if name.strip()]
    if len(cleaned_sides) < 2:
        raise ValidationError("ต้องระบุตัวเลือกสำหรับอภิปรายอย่างน้อย 2 ตัวเลือก")

    topic = form.save(commit=False)
    topic.created_by = user
    topic.save()

    sides_to_create = [Side(topic=topic, name=name) for name in cleaned_sides]
    Side.objects.bulk_create(sides_to_create)

    tags_string = form.cleaned_data.get("tags_string", "")
    if tags_string:
        tag_names = [t.strip() for t in tags_string.split(",") if t.strip()]
        for t_name in tag_names:
            tag, _ = Tag.objects.get_or_create(name=t_name)
            topic.tags.add(tag)

    return topic


@transaction.atomic
def submit_vote(user, topic, side_id, comment_text):
    """บันทึกการโหวตพร้อมล็อกแถว (Row Locking) ป้องกัน Race Condition"""
    if not side_id:
        raise ValidationError("กรุณาเลือกฝั่งก่อนลงคะแนน")

    locked_topic = Topic.objects.select_for_update().get(id=topic.id)

    if locked_topic.is_expired():
        raise ValidationError("ไม่สามารถลงคะแนนได้ เนื่องจากหัวข้อนี้ปิดการโหวตแล้ว")

    if Comment.objects.filter(topic=locked_topic, author=user).exists():
        raise ValidationError("คุณได้ลงคะแนนในหัวข้อนี้ไปแล้ว")

    try:
        side = Side.objects.get(id=side_id, topic=locked_topic)
    except Side.DoesNotExist:
        raise ValidationError("ไม่พบตัวเลือกที่ระบุ")

    return Comment.objects.create(
        topic=locked_topic,
        side=side,
        author=user,
        text=comment_text,
    )


@transaction.atomic
def update_topic(topic, form):
    """อัปเดตข้อมูลกระทู้"""
    Topic.objects.select_for_update().get(id=topic.id)
    return form.save()


@transaction.atomic
def close_topic_voting(user, topic):
    """ปิดรับการโหวตทันที โดยตรวจสอบสิทธิ์ผู้สร้างและใช้ Row Locking"""
    locked_topic = Topic.objects.select_for_update().get(id=topic.id)
    if locked_topic.created_by != user:
        raise PermissionDenied("คุณไม่มีสิทธิ์ปิดการโหวตหัวข้อนี้")
    now = timezone.now() - timedelta(seconds=1)
    locked_topic.end_date = now
    locked_topic.save()

    topic.end_date = now
    return locked_topic


@transaction.atomic
def delete_topic_by_user(user, topic):
    """ลบกระทู้พร้อมตรวจสอบสิทธิ์ในระดับ Service Layer"""
    locked_topic = Topic.objects.select_for_update().get(id=topic.id)
    if locked_topic.created_by != user:
        raise PermissionDenied("คุณไม่มีสิทธิ์ลบหัวข้อนี้")
    locked_topic.delete()
