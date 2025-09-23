# issues/urls.py
# issues/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  
    path('create-tickets/', views.create_tickets_view, name='create_tickets'),  
    path('view-tickets/', views.view_tickets, name='view_tickets'),  
    path('update-ticket/', views.update_ticket, name='update_ticket'),  
    path('suggest_fix_for_issue/<int:ticket_id>/', views.suggest_fix_view, name='suggest_fix_for_issue'),
]
