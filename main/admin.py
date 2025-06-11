from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User admin"""
    list_display = ('email', 'first_name', 'last_name', 'institution', 'is_verified', 'date_joined')
    list_filter = ('is_verified', 'is_staff', 'is_superuser', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name', 'institution')
    ordering = ('-date_joined',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('institution', 'is_verified')}),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('email', 'first_name', 'last_name', 'institution')}),
    )
