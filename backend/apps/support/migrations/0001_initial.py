import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SupportThread",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subject", models.CharField(max_length=255, verbose_name="Тема")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "Новое"),
                            ("open", "Открыто"),
                            ("waiting_for_support", "Ожидает поддержку"),
                            ("waiting_for_client", "Ожидает клиента"),
                            ("resolved", "Решено"),
                            ("closed", "Закрыто"),
                        ],
                        default="new",
                        max_length=32,
                        verbose_name="Статус",
                    ),
                ),
                (
                    "priority",
                    models.CharField(
                        blank=True,
                        choices=[("low", "Низкий"), ("normal", "Обычный"), ("high", "Высокий")],
                        default="normal",
                        max_length=16,
                        verbose_name="Приоритет",
                    ),
                ),
                ("last_message_at", models.DateTimeField(blank=True, null=True, verbose_name="Время последнего сообщения")),
                ("first_response_at", models.DateTimeField(blank=True, null=True, verbose_name="Время первого ответа")),
                ("resolved_at", models.DateTimeField(blank=True, null=True, verbose_name="Время решения")),
                ("closed_at", models.DateTimeField(blank=True, null=True, verbose_name="Время закрытия")),
                (
                    "assigned_staff",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assigned_support_threads",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Ответственный сотрудник",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="support_threads",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Клиент",
                    ),
                ),
            ],
            options={
                "verbose_name": "Обращение в поддержку",
                "verbose_name_plural": "Обращения в поддержку",
                "ordering": ("-last_message_at", "-created_at"),
            },
        ),
        migrations.CreateModel(
            name="SupportMessage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "author_side",
                    models.CharField(
                        choices=[("customer", "Клиент"), ("staff", "Сотрудник"), ("system", "Система")],
                        max_length=16,
                        verbose_name="Сторона автора",
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[("message", "Сообщение"), ("system_event", "Системное событие")],
                        default="message",
                        max_length=24,
                        verbose_name="Тип записи",
                    ),
                ),
                ("body", models.TextField(blank=True, verbose_name="Текст")),
                ("event_code", models.CharField(blank=True, default="", max_length=64, verbose_name="Код события")),
                ("event_payload", models.JSONField(blank=True, default=dict, verbose_name="Данные события")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("edited_at", models.DateTimeField(blank=True, null=True, verbose_name="Изменено")),
                (
                    "author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="support_messages",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Автор",
                    ),
                ),
                (
                    "thread",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="support.supportthread",
                        verbose_name="Обращение",
                    ),
                ),
            ],
            options={
                "verbose_name": "Сообщение поддержки",
                "verbose_name_plural": "Сообщения поддержки",
                "ordering": ("created_at", "id"),
            },
        ),
        migrations.CreateModel(
            name="SupportThreadParticipantState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_read_at", models.DateTimeField(blank=True, null=True, verbose_name="Время чтения")),
                ("unread_count", models.PositiveIntegerField(default=0, verbose_name="Непрочитанных")),
                (
                    "last_read_message",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="read_states",
                        to="support.supportmessage",
                        verbose_name="Последнее прочитанное сообщение",
                    ),
                ),
                (
                    "thread",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="participant_states",
                        to="support.supportthread",
                        verbose_name="Обращение",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="support_thread_states",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Пользователь",
                    ),
                ),
            ],
            options={
                "verbose_name": "Состояние участника обращения",
                "verbose_name_plural": "Состояния участников обращений",
            },
        ),
        migrations.AddIndex(
            model_name="supportthread",
            index=models.Index(fields=["customer", "status"], name="sup_thr_cust_status_idx"),
        ),
        migrations.AddIndex(
            model_name="supportthread",
            index=models.Index(fields=["assigned_staff", "status"], name="sup_thr_staff_status_idx"),
        ),
        migrations.AddIndex(
            model_name="supportthread",
            index=models.Index(fields=["status", "last_message_at"], name="sup_thr_status_lastmsg_idx"),
        ),
        migrations.AddIndex(
            model_name="supportthread",
            index=models.Index(fields=["created_at"], name="sup_thr_created_idx"),
        ),
        migrations.AddIndex(
            model_name="supportmessage",
            index=models.Index(fields=["thread", "created_at"], name="support_msg_thread_created_idx"),
        ),
        migrations.AddIndex(
            model_name="supportmessage",
            index=models.Index(fields=["author_side", "created_at"], name="support_msg_side_created_idx"),
        ),
        migrations.AddConstraint(
            model_name="supportthreadparticipantstate",
            constraint=models.UniqueConstraint(fields=("thread", "user"), name="sup_state_thread_user_uniq"),
        ),
        migrations.AddIndex(
            model_name="supportthreadparticipantstate",
            index=models.Index(fields=["user", "unread_count"], name="sup_state_user_unread_idx"),
        ),
        migrations.AddIndex(
            model_name="supportthreadparticipantstate",
            index=models.Index(fields=["thread", "user"], name="sup_state_thread_user_idx"),
        ),
    ]
