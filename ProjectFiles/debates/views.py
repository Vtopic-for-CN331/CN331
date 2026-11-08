from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import selectors, services
from .forms import CustomSignupForm, EditTopicForm, TopicForm


def topic_list(request):
    """หน้าหลักแสดงรายการกระทู้ทั้งหมด"""
    search_query = request.GET.get("q", "")
    show_all = request.GET.get("show_all") == "true"
    hide_expired = not show_all
    topics = selectors.get_topics(search_query, hide_expired)
    return render(
        request,
        "debates/topic_list.html",
        {
            "topics": topics,
            "search_query": search_query,
            "hide_expired": hide_expired,
            "show_all": show_all,
        },
    )


def topic_detail(request, topic_id):
    """หน้ารายละเอียดกระทู้ ส่งผลโหวต และแสดงความคิดเห็น"""
    try:
        topic = selectors.get_topic(topic_id)
    except Exception:
        return redirect("topic_list")

    if request.user.is_authenticated:
        user_vote = selectors.get_user_vote(request.user, topic)
    else:
        user_vote = None

    comments = topic.comments.all()
    selected_side_id = request.GET.get("side_filter")
    if selected_side_id and selected_side_id.isdigit():
        comments = comments.filter(side_id=int(selected_side_id))

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        try:
            services.submit_vote(
                user=request.user,
                topic=topic,
                side_id=request.POST.get("side"),
                comment_text=request.POST.get("comment_text", "").strip(),
            )
            messages.success(request, "บันทึกคะแนนและความคิดเห็นแล้ว")
        except ValidationError as err:
            err_msg = err.messages[0] if hasattr(err, "messages") else str(err)
            messages.error(request, err_msg)

        return redirect("topic_detail", topic_id=topic.id)

    return render(
        request,
        "debates/topic_detail.html",
        {
            "topic": topic,
            "user_vote": user_vote,
            "comments": comments,
            "selected_side_id": selected_side_id,
        },
    )


def signup(request):
    """สมัครสมาชิกใหม่"""
    if request.user.is_authenticated:
        return redirect("topic_list")

    if request.method == "POST":
        form = CustomSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("topic_list")
    else:
        form = CustomSignupForm()
    return render(request, "debates/signup.html", {"form": form})


@login_required
def create_topic(request):
    """หน้าสร้างกระทู้ใหม่"""
    if request.method == "POST":
        form = TopicForm(request.POST)
        side_names = request.POST.getlist("sides")
        if form.is_valid():
            try:
                services.create_topic_with_sides(request.user, form, side_names)
            except ValidationError as err:
                form.add_error(None, err)
            else:
                return redirect("topic_list")
    else:
        form = TopicForm()
        side_names = ["", ""]

    if not side_names:
        side_names = ["", ""]
    return render(
        request,
        "debates/create_topic.html",
        {"form": form, "side_names": side_names},
    )


@login_required
@require_POST
def delete_topic(request, topic_id):
    """ลบกระทู้"""
    topic = selectors.get_topic(topic_id)
    try:
        services.delete_topic_by_user(request.user, topic)
    except PermissionDenied as e:
        messages.error(request, str(e))
    return redirect("topic_list")


@login_required
def edit_topic(request, topic_id):
    """หน้าแก้ไขกระทู้และปิดการโหวต"""
    topic = selectors.get_topic(topic_id)
    if request.user != topic.created_by:
        raise PermissionDenied("คุณไม่มีสิทธิ์แก้ไขหัวข้อนี้")

    if request.method == "POST":
        if request.POST.get("action") == "close_voting":
            services.close_topic_voting(request.user, topic)
            return redirect("topic_detail", topic_id=topic.id)

        form = EditTopicForm(request.POST, instance=topic)
        if form.is_valid():
            services.update_topic(topic, form)
            return redirect("topic_detail", topic_id=topic.id)
    else:
        form = EditTopicForm(instance=topic)

    return render(request, "debates/edit_topic.html", {"form": form, "topic": topic})


@login_required
def user_profile(request):
    """หน้าโปรไฟล์ส่วนตัวของผู้ใช้"""
    my_topics = selectors.get_user_topics(request.user)
    my_comments = selectors.get_user_comments(request.user)
    return render(
        request,
        "debates/profile.html",
        {"my_topics": my_topics, "my_comments": my_comments},
    )
