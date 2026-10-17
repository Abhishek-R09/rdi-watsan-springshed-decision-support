import os

bind = f"0.0.0.0:{int(os.environ.get('PORT', '10000'))}"
workers = 1  # One shared GIS session. Multiple workers duplicate all the raster data.
worker_class = 'gthread'
threads = 4  # Health and map requests remain responsive during an assessment.
timeout = 600
graceful_timeout = 30
accesslog = '-'
errorlog = '-'
preload_app = False
