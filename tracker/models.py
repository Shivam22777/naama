from django.db import models
from django.utils import timezone

class Route(models.Model):
    route_id = models.CharField(max_length=50, primary_key=True)
    route_name = models.CharField(max_length=200)
    service_type = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.route_id} - {self.route_name} ({self.service_type})"

class BusStop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='stops')
    stop_seq = models.IntegerField()
    stop_village_name = models.CharField(max_length=200)
    district = models.CharField(max_length=100)
    taluk = models.CharField(max_length=100)
    stop_category = models.CharField(max_length=100)
    cumulative_dist_km = models.FloatField()
    stop_dwell_min = models.IntegerField()
    cumulative_travel_time_min = models.IntegerField()
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['stop_seq']
        unique_together = ['route', 'stop_seq']

    def __str__(self):
        return f"[{self.route.route_id}] #{self.stop_seq} {self.stop_village_name}"

class Driver(models.Model):
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, unique=True)
    password = models.CharField(max_length=256)
    bus_number = models.CharField(max_length=30, blank=True, default='')
    route = models.ForeignKey(Route, on_delete=models.SET_NULL, null=True, blank=True, related_name='drivers')
    start_stop = models.ForeignKey(BusStop, on_delete=models.SET_NULL, null=True, blank=True, related_name='driver_start_stops')
    destination_stop = models.ForeignKey(BusStop, on_delete=models.SET_NULL, null=True, blank=True, related_name='driver_dest_stops')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.phone_number}) - Bus: {self.bus_number}"

class Passenger(models.Model):
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, unique=True)
    password = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.phone_number})"

class Trip(models.Model):
    STATUS_CHOICES = [
        ('LIVE', 'Live'),
        ('STOPPED', 'Stopped'),
        ('DELAYED', 'Delayed'),
        ('ENDED', 'Ended'),
    ]

    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='trips')
    bus_number = models.CharField(max_length=30)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='trips')
    start_stop = models.ForeignKey(BusStop, on_delete=models.CASCADE, related_name='trip_start_stops')
    destination_stop = models.ForeignKey(BusStop, on_delete=models.CASCADE, related_name='trip_dest_stops')
    
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    current_latitude = models.FloatField(null=True, blank=True)
    current_longitude = models.FloatField(null=True, blank=True)
    current_stop_seq = models.IntegerField(default=1)
    last_location_update = models.DateTimeField(auto_now=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='LIVE')
    stopped_since = models.DateTimeField(null=True, blank=True)
    stop_reason = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Trip #{self.id} - {self.bus_number} ({self.status}) - {self.started_at.strftime('%d %b %Y %H:%M')}"

class TripStopEvent(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='stop_events')
    reason = models.CharField(max_length=200)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"StopEvent on Trip #{self.trip.id}: {self.reason} at {self.started_at}"
