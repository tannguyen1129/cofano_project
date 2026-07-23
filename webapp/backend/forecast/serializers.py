from rest_framework import serializers
from .models import Station, ProductMap, Forecast, BenchmarkMetric, PenaltyResult, Kpi


class StationSerializer(serializers.ModelSerializer):
    class Meta: model = Station; fields = ["code","name","brand","country","lat","lon","total_demand"]


class ProductMapSerializer(serializers.ModelSerializer):
    class Meta: model = ProductMap; fields = ["code","fuel","volume_share","is_main"]


class ForecastSerializer(serializers.ModelSerializer):
    station = serializers.CharField(source="station.code")
    class Meta: model = Forecast; fields = ["date","station","product","fuel","weeks_ahead","p50","p90","p95"]


class BenchmarkSerializer(serializers.ModelSerializer):
    class Meta: model = BenchmarkMetric; fields = ["model_name","wape","wape_main","wape_minor"]


class PenaltySerializer(serializers.ModelSerializer):
    class Meta:
        model = PenaltyResult
        fields = ["policy","stockout_days","shortfall","carryover","undeliverable","replan_events","penalty","vs_naive"]


class KpiSerializer(serializers.ModelSerializer):
    class Meta: model = Kpi; fields = ["key","value","label_vi","label_en"]
