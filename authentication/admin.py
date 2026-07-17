from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Profile",
            {
                "fields": (
                    "bio",
                    "avatar",
                    "is_verified",
                    "created_at",
                )
            },
        ),
    )

    readonly_fields = ("created_at",)

    list_display = (
        "email",
        "username",
        "is_verified",
        "is_staff",
        "is_active",
    )