from django.db import models

class Report(models.Model):
    uuid = models.CharField(max_length=64, unique=True)
    path = models.CharField(max_length=255)
    created_at = models.DateTimeField()
    report_url = models.URLField()

    total = models.IntegerField(default=0)
    passed = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.path} — {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"


class TestSuite(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    passed = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class TestCase(models.Model):
    suite = models.ForeignKey(TestSuite, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20)
    duration = models.FloatField(default=0)

    def __str__(self):
        return f"{self.name} [{self.status}]"
