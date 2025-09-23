# issues/models.py
from django.db import models

class Ticket(models.Model):
    repo = models.CharField(max_length=255)
    owner = models.CharField(max_length=255)
    issue_number = models.IntegerField()
    title = models.CharField(max_length=500)
    body = models.TextField()
    labels = models.JSONField()
    type = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.repo}#{self.issue_number} - {self.title}"
