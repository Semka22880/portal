import requests
from datetime import datetime
from .models import Report, TestSuite, TestCase

BASE_URL = "http://10.177.140.34:8080/allure"

def import_report(uuid: str):
    url = f"{BASE_URL}/reports/{uuid}/widgets/summary.json"
    overview = requests.get(url).json()

    report = Report.objects.update_or_create(
        uuid=uuid,
        defaults={
            "path": overview.get("reportName", ""),
            "created_at": datetime.now(),
            "report_url": f"{BASE_URL}/reports/{uuid}",
            "total": overview["statistic"]["total"],
            "passed": overview["statistic"]["passed"],
            "failed": overview["statistic"]["failed"],
            "skipped": overview["statistic"]["skipped"],
            "success_rate": overview["statistic"]["passed"] / max(1, overview["statistic"]["total"]) * 100,
        }
    )[0]

    # Suites
    suites_data = requests.get(f"{BASE_URL}/reports/{uuid}/widgets/suites.json").json()
    for s in suites_data:
        suite = TestSuite.objects.create(
            report=report,
            name=s["name"],
            passed=s["statistic"]["passed"],
            failed=s["statistic"]["failed"],
            skipped=s["statistic"]["skipped"],
        )
        for t in s["children"]:
            TestCase.objects.create(
                suite=suite,
                name=t["name"],
                status=t["status"],
                duration=t.get("time", {}).get("duration", 0)
            )

    return report
