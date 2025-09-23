# issues/views.py
from django.shortcuts import render
from django.http import JsonResponse
from issues.services.adk_integration import get_issues_from_url
import logging
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
import json
from django.http import JsonResponse
from .models import Ticket
from issues.services.suggest_fix_integration import get_suggested_fix_for_issue
from django.shortcuts import get_object_or_404, render
logger = logging.getLogger(__name__)

def home(request):
    return render(request, "home.html")


def create_tickets_view(request):
    url = request.GET.get("url")
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")

    if not url:
        return JsonResponse({"error": "No URL provided"}, status=400)

    # Parse dates safely
    start_date = None
    end_date = None
    date_format = "%Y-%m-%d"
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, date_format)
        if end_date_str:
            end_date = datetime.strptime(end_date_str, date_format)
        if start_date and end_date and start_date > end_date:
            return JsonResponse({"error": "Start date cannot be after end date"}, status=400)
    except ValueError:
        return JsonResponse({"error": "Invalid date format, expected MM/DD/YYYY"}, status=400)

    try:
        # Fetch issues from ADK agent
        issues = get_issues_from_url(url)

        logger.info(f"Received issues data: {issues}")

        if not issues:
            return JsonResponse({"error": "No issues found"}, status=404)

        # Check if the first issue has an error
        if len(issues) > 0 and "error" in issues[0]:
            return JsonResponse({
                "error": "Agent failed to fetch issues",
                "details": issues[0]
            }, status=500)

        # Filter by date if created_at is available
        if start_date or end_date:
            filtered_issues = []
            for issue in issues:
                # If the agent provides 'created_at', filter by it
                created_str = issue.get("created_at")
                if created_str:
                    created_at = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%SZ")
                    if start_date and created_at < start_date:
                        continue
                    if end_date and created_at > end_date:
                        continue
                filtered_issues.append(issue)
            issues = filtered_issues

        issues = issues[:10]

        saved_tickets = []
        for issue in issues:
            # Validate required fields
            required_fields = ['repo', 'owner', 'issue_number', 'title', 'body']
            missing_fields = [field for field in required_fields if field not in issue]

            if missing_fields:
                logger.warning(f"Issue missing required fields {missing_fields}: {issue}")
                issue = fill_missing_fields(issue, url)
                missing_fields = [field for field in required_fields if field not in issue]
                if missing_fields:
                    logger.error(f"Still missing fields {missing_fields} after processing: {issue}")
                    continue

            try:
                ticket, created = Ticket.objects.get_or_create(
                    repo=issue["repo"],
                    owner=issue["owner"],
                    issue_number=issue["issue_number"],
                    defaults={
                        "title": issue["title"][:500],
                        "body": issue["body"][:1000] if issue["body"] else "",
                        "labels": issue.get("labels", []),
                        "type": issue.get("type", "issue")
                    }
                )
                saved_tickets.append(ticket.id)
                logger.info(f"{'Created' if created else 'Found existing'} ticket: {ticket}")
            except Exception as e:
                logger.error(f"Error saving ticket for issue {issue}: {str(e)}")
                continue

        if not saved_tickets:
            return JsonResponse({
                "error": "No tickets could be saved",
                "details": "Issues may be missing required fields or filtered out by date"
            }, status=400)

        return JsonResponse({
            "saved_ticket_ids": saved_tickets,
            "total_processed": len(issues),
            "total_saved": len(saved_tickets)
        })

    except Exception as e:
        logger.error(f"Error in create_tickets_view: {str(e)}")
        return JsonResponse({
            "error": "Internal server error",
            "details": str(e)
        }, status=500)


def fill_missing_fields(issue, url):
    """Try to fill missing fields from URL and issue data"""
    import re

    github_match = re.match(r'https://github\.com/([^/]+)/([^/]+)', url)
    if github_match:
        if 'owner' not in issue:
            issue['owner'] = github_match.group(1)
        if 'repo' not in issue:
            issue['repo'] = github_match.group(2)

    issue_match = re.search(r'/issues/(\d+)', url)
    if issue_match and 'issue_number' not in issue:
        issue['issue_number'] = int(issue_match.group(1))

    if 'title' not in issue:
        issue['title'] = f"Issue from {url}"
    if 'body' not in issue:
        issue['body'] = ""

    return issue


def view_tickets(request):
    tickets = Ticket.objects.all().order_by("-created_at")
    return render(request, "view_tickets.html", {"tickets": tickets})



@csrf_exempt
def update_ticket(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)
    try:
        data = json.loads(request.body)
        ticket = Ticket.objects.get(id=data['ticket_id'])
        field = data['field']
        value = data['value']

        if field == "status":
            ticket.status = value
        elif field == "assignee":
            from django.contrib.auth.models import User
            ticket.assignee = User.objects.get(id=value) if value else None
        ticket.save()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
def suggest_fix_view(request, ticket_id):
    """
    Display the suggested fix for a ticket/issue.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    # Fetch suggested fix from the agent
    suggested_fix_data = get_suggested_fix_for_issue(ticket.id)
    
    return render(request, "suggest_fix.html", {
        "ticket": ticket,
        "suggested_fix": suggested_fix_data
    })