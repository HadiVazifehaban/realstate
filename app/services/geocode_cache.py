"""Reverse-geocoding client: grid cache in front of OSM Nominatim.

The office node runs offline-first, so a geocoder outage must degrade
gracefully (an empty district) rather than block a submission.
"""

from app.services.osm_service import cached_nominatim_reverse_geocode as cached_reverse_geocode

__all__ = ["cached_reverse_geocode"]