from django.urls import path
from . import views

urlpatterns = [
    path("kpis", views.kpis),
    path("stations", views.stations),
    path("products", views.products),
    path("benchmark", views.benchmark),
    path("penalty", views.penalty),
    path("forecast", views.forecast),
    path("sim", views.sim),
    path("dashboard", views.dashboard),
    path("predict/live", views.predict_live),
]
