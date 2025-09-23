# issues/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Ticket, Issue, ProcessingLog
import re

class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model (basic info only)"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']
        read_only_fields = ['id', 'username', 'first_name', 'last_name']

class ProcessingLogSerializer(serializers.ModelSerializer):
    """Serializer for ProcessingLog model"""
    
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = ProcessingLog
        fields = [
            'id', 'level', 'level_display', 'message', 
            'timestamp', 'time_ago'
        ]
        read_only_fields = ['id', 'timestamp']
    
    def get_time_ago(self, obj):
        """Calculate time since log entry"""
        from django.utils import timezone
        from django.utils.timesince import timesince
        
        return timesince(obj.timestamp, timezone.now())

class IssueSerializer(serializers.ModelSerializer):
    """Serializer for Issue model"""
    
    labels_display = serializers.ReadOnlyField()
    issue_type_display = serializers.CharField(source='get_issue_type_display', read_only=True)
    github_url_display = serializers.SerializerMethodField()
    created_at_display = serializers.SerializerMethodField()
    github_created_at_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Issue
        fields = [
            'id', 'repo', 'owner', 'issue_number', 'title', 'body',
            'labels', 'labels_display', 'issue_type', 'issue_type_display',
            'github_id', 'github_url', 'github_url_display',
            'github_created_at', 'github_created_at_display',
            'github_updated_at', 'github_state',
            'created_at', 'created_at_display'
        ]
        read_only_fields = [
            'id', 'created_at', 'labels_display', 'issue_type_display'
        ]
    
    def get_github_url_display(self, obj):
        """Format GitHub URL for display"""
        if obj.github_url:
            return obj.github_url
        return f"https://github.com/{obj.owner}/{obj.repo}/issues/{obj.issue_number}"
    
    def get_created_at_display(self, obj):
        """Format created_at for display"""
        from django.utils.dateformat import format
        return format(obj.created_at, 'M d, Y H:i')
    
    def get_github_created_at_display(self, obj):
        """Format github_created_at for display"""
        if obj.github_created_at:
            from django.utils.dateformat import format
            return format(obj.github_created_at, 'M d, Y H:i')
        return None

class IssueCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Issue instances"""
    
    class Meta:
        model = Issue
        fields = [
            'repo', 'owner', 'issue_number', 'title', 'body',
            'labels', 'issue_type', 'github_id', 'github_url',
            'github_created_at', 'github_updated_at', 'github_state'
        ]
    
    def validate_labels(self, value):
        """Validate labels field"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Labels must be a list")
        return value
    
    def validate_github_url(self, value):
        """Validate GitHub URL format"""
        if value:
            github_pattern = r'^https://github\.com/[\w\-\.]+/[\w\-\.]+/issues/\d+/?$'
            if not re.match(github_pattern, value):
                raise serializers.ValidationError("Invalid GitHub issue URL format")
        return value

class TicketSerializer(serializers.ModelSerializer):
    """Serializer for Ticket model with related data"""
    
    # Related data
    issues = IssueSerializer(many=True, read_only=True)
    logs = ProcessingLogSerializer(many=True, read_only=True)
    created_by = UserSerializer(read_only=True)
    
    # Display fields
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    ticket_type_display = serializers.CharField(source='get_ticket_type_display', read_only=True)
    created_at_display = serializers.SerializerMethodField()
    updated_at_display = serializers.SerializerMethodField()
    processing_time_display = serializers.SerializerMethodField()
    
    # Computed fields
    issues_count = serializers.SerializerMethodField()
    logs_count = serializers.SerializerMethodField()
    url_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'ticket_id', 'github_url', 'ticket_type', 'ticket_type_display',
            'status', 'status_display', 'created_by',
            'created_at', 'created_at_display',
            'updated_at', 'updated_at_display',
            'task_id', 'error_message',
            'total_issues_found', 'processing_time_seconds', 'processing_time_display',
            'issues', 'issues_count', 'logs', 'logs_count', 'url_info'
        ]
        read_only_fields = [
            'ticket_id', 'created_at', 'updated_at', 'task_id',
            'total_issues_found', 'processing_time_seconds'
        ]
    
    def get_created_at_display(self, obj):
        """Format created_at for display"""
        from django.utils.dateformat import format
        return format(obj.created_at, 'M d, Y H:i')
    
    def get_updated_at_display(self, obj):
        """Format updated_at for display"""
        from django.utils.dateformat import format
        return format(obj.updated_at, 'M d, Y H:i')
    
    def get_processing_time_display(self, obj):
        """Format processing time for display"""
        if obj.processing_time_seconds:
            seconds = obj.processing_time_seconds
            if seconds < 60:
                return f"{seconds:.1f} seconds"
            elif seconds < 3600:
                minutes = seconds / 60
                return f"{minutes:.1f} minutes"
            else:
                hours = seconds / 3600
                return f"{hours:.1f} hours"
        return None
    
    def get_issues_count(self, obj):
        """Get count of related issues"""
        return obj.issues.count()
    
    def get_logs_count(self, obj):
        """Get count of processing logs"""
        return obj.logs.count()
    
    def get_url_info(self, obj):
        """Extract information from GitHub URL"""
        try:
            url = obj.github_url
            path_parts = url.replace('https://github.com/', '').strip('/').split('/')
            
            if len(path_parts) >= 2:
                owner = path_parts[0]
                repo = path_parts[1]
                
                # Check if it's a specific issue
                if len(path_parts) >= 4 and path_parts[2] == 'issues' and path_parts[3].isdigit():
                    return {
                        'owner': owner,
                        'repo': repo,
                        'full_name': f'{owner}/{repo}',
                        'issue_number': int(path_parts[3]),
                        'type': 'single_issue'
                    }
                else:
                    return {
                        'owner': owner,
                        'repo': repo,
                        'full_name': f'{owner}/{repo}',
                        'issue_number': None,
                        'type': 'repository'
                    }
        except:
            pass
        
        return {
            'owner': None,
            'repo': None,
            'full_name': 'Unknown',
            'issue_number': None,
            'type': 'unknown'
        }

class TicketCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Ticket instances"""
    
    class Meta:
        model = Ticket
        fields = ['github_url', 'ticket_type']
    
    def validate_github_url(self, value):
        """Validate GitHub URL format"""
        github_patterns = [
            r'^https://github\.com/[\w\-\.]+/[\w\-\.]+/?$',  # Repo URL
            r'^https://github\.com/[\w\-\.]+/[\w\-\.]+/issues/?$',  # Issues list
            r'^https://github\.com/[\w\-\.]+/[\w\-\.]+/issues/\d+/?$',  # Specific issue
        ]
        
        if not any(re.match(pattern, value) for pattern in github_patterns):
            raise serializers.ValidationError(
                "Invalid GitHub URL format. Please provide a valid repository or issue URL."
            )
        
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        github_url = data.get('github_url', '')
        ticket_type = data.get('ticket_type', '')
        
        # Auto-determine ticket type if not provided
        if not ticket_type:
            if '/issues/' in github_url and github_url.split('/issues/')[-1].strip('/').isdigit():
                data['ticket_type'] = 'single_issue'
            else:
                data['ticket_type'] = 'repo_issues'
        
        # Validate ticket type matches URL
        is_single_issue = '/issues/' in github_url and github_url.split('/issues/')[-1].strip('/').isdigit()
        
        if ticket_type == 'single_issue' and not is_single_issue:
            raise serializers.ValidationError(
                "Ticket type 'single_issue' requires a URL pointing to a specific issue."
            )
        
        if ticket_type == 'repo_issues' and is_single_issue:
            raise serializers.ValidationError(
                "Ticket type 'repo_issues' cannot be used with a specific issue URL."
            )
        
        return data

class TicketSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for ticket lists/summaries"""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    ticket_type_display = serializers.CharField(source='get_ticket_type_display', read_only=True)
    created_at_display = serializers.SerializerMethodField()
    issues_count = serializers.SerializerMethodField()
    url_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'ticket_id', 'github_url', 'ticket_type', 'ticket_type_display',
            'status', 'status_display', 'created_at', 'created_at_display',
            'total_issues_found', 'processing_time_seconds',
            'issues_count', 'url_info'
        ]
    
    def get_created_at_display(self, obj):
        from django.utils.dateformat import format
        return format(obj.created_at, 'M d, Y H:i')
    
    def get_issues_count(self, obj):
        return obj.issues.count()
    
    def get_url_info(self, obj):
        """Simplified URL info for summary"""
        try:
            path_parts = obj.github_url.replace('https://github.com/', '').strip('/').split('/')
            if len(path_parts) >= 2:
                return f"{path_parts[0]}/{path_parts[1]}"
        except:
            pass
        return "Unknown"

class TicketStatsSerializer(serializers.Serializer):
    """Serializer for ticket statistics"""
    
    total_tickets = serializers.IntegerField()
    pending_tickets = serializers.IntegerField()
    processing_tickets = serializers.IntegerField()
    completed_tickets = serializers.IntegerField()
    failed_tickets = serializers.IntegerField()
    total_issues = serializers.IntegerField()
    avg_processing_time = serializers.FloatField()
    success_rate = serializers.FloatField()

class ConversationMessageSerializer(serializers.Serializer):
    """Serializer for conversation messages"""
    
    message = serializers.CharField(max_length=2000)
    
    def validate_message(self, value):
        """Validate conversation message"""
        message = value.strip()
        
        if not message:
            raise serializers.ValidationError("Message cannot be empty.")
        
        if len(message) < 5:
            raise serializers.ValidationError("Message is too short.")
        
        # Basic harmful content check
        harmful_patterns = [
            r'ignore\s+previous\s+instructions',
            r'system\s+prompt',
            r'<script',
            r'javascript:',
        ]
        
        for pattern in harmful_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                raise serializers.ValidationError("Message contains potentially harmful content.")
        
        return message

class BulkActionSerializer(serializers.Serializer):
    """Serializer for bulk actions on tickets"""
    
    ACTION_CHOICES = [
        ('delete', 'Delete'),
        ('reprocess', 'Reprocess'),
        ('mark_completed', 'Mark as Completed'),
        ('export', 'Export'),
    ]
    
    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    ticket_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=100  # Limit bulk operations
    )
    
    def validate_ticket_ids(self, value):
        """Validate ticket IDs exist"""
        existing_count = Ticket.objects.filter(ticket_id__in=value).count()
        if existing_count != len(value):
            raise serializers.ValidationError(
                f"Only {existing_count} out of {len(value)} tickets exist."
            )
        return value
    
    def validate(self, data):
        """Cross-field validation for bulk actions"""
        action = data.get('action')
        ticket_ids = data.get('ticket_ids', [])
        
        if action == 'reprocess':
            # Check if any tickets are currently processing
            processing_tickets = Ticket.objects.filter(
                ticket_id__in=ticket_ids,
                status='processing'
            ).count()
            
            if processing_tickets > 0:
                raise serializers.ValidationError(
                    f"{processing_tickets} tickets are currently processing. "
                    "Cannot reprocess tickets that are already being processed."
                )
        
        return data