from django.urls import path

from . import views

urlpatterns = [
    path("portfolio/", views.portfolio),
    path("buildings/", views.buildings),
    path("buildings/<str:loc_id>/", views.building_detail),
    path("loss-curve/", views.loss_curve),
    path("hotspots/", views.hotspots),
    path("copilot/", views.copilot),
    path("copilot/ingest/", views.ingest),
    path("copilot/report/", views.risk_report),
]
