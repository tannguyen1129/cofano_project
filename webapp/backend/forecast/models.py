from django.db import models


class Station(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=120, blank=True)
    brand = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=4, blank=True)
    lat = models.FloatField()
    lon = models.FloatField()
    total_demand = models.FloatField(default=0)

    def __str__(self): return f"{self.code} ({self.brand})"


class ProductMap(models.Model):
    code = models.CharField(max_length=4, unique=True)   # P1..P5
    fuel = models.CharField(max_length=20)
    volume_share = models.FloatField()
    is_main = models.BooleanField(default=False)

    def __str__(self): return f"{self.code}={self.fuel}"


class Forecast(models.Model):
    date = models.DateField(db_index=True)
    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="forecasts")
    product = models.CharField(max_length=4)
    fuel = models.CharField(max_length=20)
    weeks_ahead = models.IntegerField(default=1)
    p50 = models.FloatField()
    p90 = models.FloatField()
    p95 = models.FloatField()

    class Meta:
        indexes = [models.Index(fields=["station", "product", "date"])]


class BenchmarkMetric(models.Model):
    model_name = models.CharField(max_length=60)
    wape = models.FloatField()
    wape_main = models.FloatField(null=True)
    wape_minor = models.FloatField(null=True)


class PenaltyResult(models.Model):
    """Version 5 capacity-bounded simulation result (report §6.2).

    The old single `overfill` figure is split in two: `carryover` is real stock that stayed
    within tank capacity, while `undeliverable` is volume that exceeded the remaining headroom
    and would force a reroute/replan.
    """
    policy = models.CharField(max_length=30)
    stockout_days = models.IntegerField()
    shortfall = models.BigIntegerField()
    carryover = models.BigIntegerField(default=0)
    undeliverable = models.BigIntegerField(default=0)
    replan_events = models.IntegerField(default=0)
    penalty = models.BigIntegerField()
    vs_naive = models.FloatField()


class Kpi(models.Model):
    key = models.CharField(max_length=40, unique=True)
    value = models.FloatField()
    label_vi = models.CharField(max_length=200)
    label_en = models.CharField(max_length=200)
