"""
Setu's matching engine.

Core idea: a surplus post (Resource) and a need post (NeedRequest) are matched
not by "first come first served" but by a score combining:
  - urgency of the need (critical/high/medium/low)
  - proximity (closer = better, capped search radius)
  - how soon the resource expires (perishable food should move fast)
  - the requester's trust score (mild tie-breaker toward reliable users)

This is intentionally simple, explainable math -- not a black box -- so a
giver can see *why* a particular match was suggested. It could be swapped
for a learned model later without changing the surrounding app.
"""
import math
from flask import current_app


def haversine_km(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return None
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def score_pair(resource, need, receiver_trust_score=50):
    """Returns (score, distance_km) for a resource/need pair, or (0, None) if incompatible."""
    if resource.category != need.category:
        return 0, None
    if resource.status != "open" or need.status != "open":
        return 0, None

    cfg = current_app.config
    distance = haversine_km(resource.lat, resource.lng, need.lat, need.lng)

    if distance is not None and distance > cfg["MATCH_SEARCH_RADIUS_KM"]:
        return 0, distance

    score = 0.0

    # Urgency: the single biggest factor -- a critical need should nearly always outrank a low one.
    score += cfg["URGENCY_WEIGHTS"].get(need.urgency, 10)

    # Proximity: linear decay from MAX_PROXIMITY_SCORE at 0km to 0 at the search radius.
    if distance is not None:
        radius = cfg["MATCH_SEARCH_RADIUS_KM"]
        score += max(0, cfg["MAX_PROXIMITY_SCORE"] * (1 - distance / radius))
    else:
        # No location data for one side -- assume city-wide, give partial credit.
        score += cfg["MAX_PROXIMITY_SCORE"] * 0.4

    # Expiry: resources expiring soon get pushed up so perishables don't go to waste.
    hours_left = resource.hours_until_expiry
    if hours_left is not None:
        if hours_left <= 0:
            score -= 50  # already expired, effectively disqualify
        elif hours_left <= 6:
            score += cfg["MAX_EXPIRY_BONUS"]
        elif hours_left <= 24:
            score += cfg["MAX_EXPIRY_BONUS"] * 0.6
        elif hours_left <= 72:
            score += cfg["MAX_EXPIRY_BONUS"] * 0.25

    # Trust: mild nudge toward requesters who reliably confirm receipt.
    score += cfg["MAX_TRUST_BONUS"] * (receiver_trust_score / 100)

    return round(score, 1), (round(distance, 1) if distance is not None else None)


def best_needs_for_resource(resource, candidate_needs, limit=5):
    """Rank open NeedRequests against one Resource. candidate_needs: iterable of NeedRequest."""
    scored = []
    for need in candidate_needs:
        s, d = score_pair(resource, need, receiver_trust_score=need.requester.trust_score or 50)
        if s > 0:
            scored.append((s, d, need))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:limit]


def best_resources_for_need(need, candidate_resources, limit=5):
    """Rank open Resources against one NeedRequest."""
    scored = []
    for resource in candidate_resources:
        s, d = score_pair(resource, need, receiver_trust_score=need.requester.trust_score or 50)
        if s > 0:
            scored.append((s, d, resource))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:limit]
