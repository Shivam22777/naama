from django.contrib import admin
from tracker.models import Route, BusStop, Driver, Passenger, Trip, TripStopEvent

@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('route_id', 'route_name', 'service_type')
    search_fields = ('route_id', 'route_name', 'service_type')

@admin.register(BusStop)
class BusStopAdmin(admin.ModelAdmin):
    list_display = ('route', 'stop_seq', 'stop_village_name', 'district', 'taluk', 'cumulative_dist_km', 'cumulative_travel_time_min')
    list_filter = ('route', 'district')
    search_fields = ('stop_village_name', 'district', 'taluk')

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'bus_number', 'route', 'start_stop', 'destination_stop', 'created_at')
    search_fields = ('name', 'phone_number', 'bus_number')
    list_filter = ('route',)

@admin.register(Passenger)
class PassengerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'created_at')
    search_fields = ('name', 'phone_number')

@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('id', 'bus_number', 'driver', 'route', 'status', 'started_at', 'ended_at', 'stop_reason', 'last_location_update')
    list_filter = ('status', 'route')
    search_fields = ('bus_number', 'driver__name', 'stop_reason')

@admin.register(TripStopEvent)
class TripStopEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'trip', 'reason', 'started_at', 'resolved_at')
    list_filter = ('reason',)
