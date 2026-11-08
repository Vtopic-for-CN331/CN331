from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="ชื่อแท็ก")

    def __str__(self):
        return self.name


class Topic(models.Model):
    title = models.CharField(max_length=200, verbose_name="หัวข้อกระทู้")
    description = models.TextField(verbose_name="รายละเอียดประเด็น")
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="ผู้ตั้งกระทู้"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    tags = models.ManyToManyField(
        Tag, blank=True, related_name="topics", verbose_name="แท็ก"
    )
    is_anonymous = models.BooleanField(
        default=False,
        verbose_name="ตั้งหัวข้อแบบไม่ระบุตัวตน",
    )

    @property
    def vote_count(self):
        # นับรวมคอมเมนต์ทั้งหมดในกระทู้นี้ที่มีการโหวตเลือกฝั่ง
        return self.comments.filter(side__isnull=False).count()

    def is_expired(self):
        if self.end_date:
            return timezone.now() >= self.end_date
        return False

    def time_left_display(self):
        if not self.end_date:
            return ""

        now = timezone.now()
        if now >= self.end_date:
            return "หมดเวลาแล้ว"

        diff = self.end_date - now
        days = diff.days
        seconds = diff.seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60

        time_parts = []
        if days > 0:
            time_parts.append(f"{days} วัน")
        if hours > 0:
            time_parts.append(f"{hours} ชั่วโมง")
        if minutes > 0:
            time_parts.append(f"{minutes} นาที")

        if not time_parts:
            return "เหลือเวลาไม่ถึง 1 นาที"

        return f"เหลือเวลา {' '.join(time_parts)}"

    def __str__(self):
        return self.title


class Side(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="sides")
    name = models.CharField(
        max_length=100, verbose_name="ชื่อฝั่ง (เช่น เห็นด้วย/ไม่เห็นด้วย)"
    )

    @property
    def vote_count(self):
        # นับจำนวนโหวตเฉพาะฝั่งนี้
        return self.comment_set.count()

    @property
    def percentage(self):
        total_topic_votes = self.topic.vote_count
        if total_topic_votes == 0:
            return 0.0
        # บังคับแปลงเป็น float ก่อนหาร เพื่อไม่ให้โดน PostgreSQL ปัดเศษทิ้งเป็น 0
        return round((float(self.vote_count) / float(total_topic_votes)) * 100, 1)

    def __str__(self):
        return f"{self.topic.title} - {self.name}"


class Comment(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="ผู้คอมเมนต์"
    )
    side = models.ForeignKey(
        Side,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="ฝั่งที่เลือกโหวต",
    )
    text = models.TextField(verbose_name="ความคิดเห็น")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("topic", "author"),
                condition=models.Q(side__isnull=False),
                name="unique_vote_per_user_topic",
            )
        ]

    def __str__(self):
        return f"Comment by {self.author.username} on {self.topic.title}"
