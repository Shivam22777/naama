import csv
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from tracker.models import Route, BusStop

# Standard lat/lon coordinates for Karnataka bus stops in dataset
STOP_COORDINATES = {
    "Kempegowda Bus Station (Majestic)": (12.9779, 77.5724),
    "Kengeri TTMC": (12.9081, 77.4764),
    "Bidadi": (12.7947, 77.3850),
    "Ramanagara Bus Stand": (12.7209, 77.2804),
    "Channapatna Bus Stand": (12.6517, 77.2078),
    "Maddur Bus Stand": (12.5857, 77.0450),
    "Mandya KSRTC Bus Stand": (12.5255, 76.8954),
    "Srirangapatna Bus Stand": (12.4233, 76.6946),
    "Mysuru KSRTC Suburb Stand": (12.3106, 76.6575),
    "Yeshwantpur TTMC": (13.0280, 77.5552),
    "Dasarahalli": (13.0441, 77.5140),
    "Nelamangala Bus Stand": (13.0984, 77.3916),
    "Kulavanahalli Cross": (13.1764, 77.2882),
    "Dobbspet (Sompura)": (13.2355, 77.2405),
    "Kyathsandra": (13.3150, 77.1350),
    "Tumakuru KSRTC Bus Stand": (13.3392, 77.1018),
    "Yadgir City Central Bus Stand": (16.7631, 77.1365),
    "Hattikuni Village": (16.8524, 77.1420),
    "Saidapur Cross": (16.5510, 77.2612),
    "Shahapur Bus Stand": (16.7032, 76.8407),
    "Belagavi City CBT": (15.8497, 74.5089),
    "Suvarna Vidhana Soudhа": (15.8580, 74.5950),
    "Suvarna Vidhana Soudha": (15.8580, 74.5950),
    "Kondaskoppa Village": (15.7725, 74.6510),
    "Kittur Toll Plaza / Bus Stop": (15.5975, 74.7892),
    "Narendra Cross / Bypass": (15.4950, 74.9810),
    "Vijayapura (Bijapur) City Bus Stand": (16.8302, 75.7100),
    "Kavalagi Village": (16.8850, 75.8420),
    "Sindagi KSRTC Bus Stand": (16.9181, 76.2338),
    "Jevargi Bus Stand": (17.0188, 76.7728),
    "Kalaburagi Central Bus Stand": (17.3297, 76.8343),
    "Bidar City Central Bus Stand": (17.9104, 77.5199),
    "Bagdal Village": (17.8420, 77.3550),
    "Mannaekhelli Cross": (17.7540, 77.2710),
    "Chimkod Cross": (17.5850, 77.4120),
    "Chincholi Bus Stand": (17.4660, 77.4320),
    "Raichur District Bus Stand": (16.2076, 77.3550),
    "Gabbur Cross": (16.1850, 77.1320),
    "Pachedoddi Village": (16.2100, 77.0120),
    "Devadurga Town Bus Stand": (16.4250, 76.9380),
}

class Command(BaseCommand):
    help = 'Import routes and bus stops from bus_routes_dataset.csv'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', nargs='?', type=str, default='bus_routes_dataset.csv')

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        if not os.path.isabs(csv_path):
            csv_path = os.path.join(settings.BASE_DIR, csv_path)

        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f"CSV file not found at {csv_path}"))
            return

        routes_created = 0
        stops_created = 0

        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                route_id = row['Route_ID'].strip()
                route_name = row['Route_Name'].strip()
                service_type = row['Service_Type'].strip()

                route_obj, created_route = Route.objects.get_or_create(
                    route_id=route_id,
                    defaults={
                        'route_name': route_name,
                        'service_type': service_type,
                    }
                )
                if created_route:
                    routes_created += 1

                stop_seq = int(row['Stop_Seq'].strip())
                village_name = row['Stop_Village_Name'].strip()
                district = row['District'].strip()
                taluk = row['Taluk'].strip()
                stop_cat = row['Stop_Category'].strip()
                cum_dist = float(row['Cumulative_Dist_km'].strip())
                stop_dwell = int(row['Stop_Dwell_min'].strip())
                cum_time = int(row['Cumulative_Travel_Time_min'].strip())

                lat, lon = STOP_COORDINATES.get(village_name, (None, None))

                BusStop.objects.update_or_create(
                    route=route_obj,
                    stop_seq=stop_seq,
                    defaults={
                        'stop_village_name': village_name,
                        'district': district,
                        'taluk': taluk,
                        'stop_category': stop_cat,
                        'cumulative_dist_km': cum_dist,
                        'stop_dwell_min': stop_dwell,
                        'cumulative_travel_time_min': cum_time,
                        'latitude': lat,
                        'longitude': lon,
                    }
                )
                stops_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully imported dataset! Routes: {routes_created} new, Total Stop Records: {stops_created}"
        ))
