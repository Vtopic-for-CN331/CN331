from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils.safestring import mark_safe

from .models import Topic


class TopicForm(forms.ModelForm):
    tags_string = forms.CharField(
        required=False,
        label="แท็ก (Tags)",
        help_text="",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Topic
        fields = [
            "title",
            "is_anonymous",
            "description",
            "end_date",
            "tags_string",
        ]
        labels = {
            "title": "ชื่อหัวข้อใหม่",
            "description": "รายละเอียด",
            "end_date": "เวลาปิดรับโหวต (ปล่อยว่างได้ถ้าไม่จำกัด)",
        }
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "end_date": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
            "is_anonymous": forms.CheckboxInput(
                attrs={"class": "form-check-input", "role": "switch"}
            ),
        }


class EditTopicForm(forms.ModelForm):
    tags_string = forms.CharField(
        required=False,
        label="แท็ก (Tags)",
        help_text="",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Topic
        fields = ["title", "description", "is_anonymous"]
        labels = {
            "title": "ชื่อหัวข้อ",
            "description": "รายละเอียด",
        }
        widgets = {
            "is_anonymous": forms.CheckboxInput(
                attrs={"class": "form-check-input mt-2 mb-3"}
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            existing_tags = self.instance.tags.values_list("name", flat=True)
            self.initial["tags_string"] = ", ".join(existing_tags)


class CustomSignupForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username"]
        labels = {
            "username": "ชื่อผู้ใช้",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = ""
        password_help_html = (
            '<ul style="padding-left: 20px; margin-top: 5px; '
            'color: #6c757d; font-size: 0.9em;">\n'
            "    <li>รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร</li>\n"
            "    <li>รหัสผ่านต้องไม่ประกอบด้วยตัวเลขเพียงอย่างเดียว</li>\n"
            "</ul>"
        )
        self.fields["password1"].help_text = mark_safe(password_help_html)  # nosec B308
        help_text_p2 = (
            '<span style="color: #6c757d; font-size: 0.9em;">'
            "กรอกรหัสผ่านอีกครั้ง</span>"
        )
        self.fields["password2"].help_text = mark_safe(help_text_p2)  # nosec B308
