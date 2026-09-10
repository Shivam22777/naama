from django.urls import path
from tracker import views

urlpatterns = [
    path('', views.home, name='home'),
    
    # Driver URLs
    path('driver/register/', views.driver_register, name='driver_register'),
    path('driver/login/', views.driver_login, name='driver_login'),
    path('driver/logout/', views.driver_logout, name='driver_logout'),
    path('driver/dashboard/', views.driver_dashboard, name='driver_dashboard'),

    # Passenger URLs
    path('passenger/register/', views.user_register, name='user_register'),
    path('passenger/login/', views.user_login, name='user_login'),
    path('passenger/logout/', views.user_logout, name='user_logout'),
    path('passenger/dashboard/', views.user_dashboard, name='user_dashboard'),

    # APIs
    path('api/route-stops/<str:route_id>/', views.api_get_route_stops, name='api_route_stops'),
    path('api/valid-destinations/', views.api_get_valid_destinations, name='api_valid_destinations'),
    path('api/start-journey/', views.api_start_journey, name='api_start_journey'),
    path('api/end-journey/', views.api_end_journey, name='api_end_journey'),
    path('api/update-location/', views.api_update_location, name='api_update_location'),
    path('api/report-stop-reason/', views.api_report_stop_reason, name='api_report_stop_reason'),
    path('api/resume-journey/', views.api_resume_journey, name='api_resume_journey'),
    path('api/bus-location/<int:bus_id>/', views.api_bus_location, name='api_bus_location'),
    path('api/search-buses/', views.api_search_buses, name='api_search_buses'),
]
