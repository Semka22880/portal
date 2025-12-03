from django.db import models

class Build(models.Model):
    build_number = models.CharField(max_length=50)  # Номер билда, e.g., 'SMK-MOB-T17-593'
    date = models.DateField(null = True, blank = True)  # Дата билда
    created_at = models.DateTimeField(auto_now_add=True)
    uuid = models.CharField(max_length=50, unique = True, blank=True, null = True)
    build_type=models.CharField(max_length=59, default='Other', db_index=True)

    def __str__(self):
        return f"Build {self.build_number} ({self.date})"

class TestRun(models.Model):
    build = models.ForeignKey(
        Build,
        on_delete=models.CASCADE,
        related_name='test_runs'
    )
    architecture = models.CharField(max_length=50)
    run_date = models.DateField(null =True, blank = True)
    allure_report_url = models.URLField()
    total_tests = models.IntegerField(default=0)
    passed_tests = models.IntegerField(default=0)
    failed_tests = models.IntegerField(default=0)
    skipped_tests = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.build.build_number} — {self.architecture}"

class TestCaseRun(models.Model):
    test_run = models.ForeignKey(
        TestRun,
        on_delete=models.CASCADE,
        related_name='cases'
    )
    test_name = models.CharField(max_length=500)
    status = models.CharField(max_length=20)
    execution_date = models.DateField()
    architecture = models.CharField(max_length=50, default='Other')

    def __str__(self):
        return f"{self.test_name} — {self.status}"