from django.contrib import admin
from .models import Ticket  # only import what exists

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("repo", "owner", "issue_number", "title", "type")
