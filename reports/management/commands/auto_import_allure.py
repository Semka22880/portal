# reports/management/commands/auto_import_allure.py

import csv
import io
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from reports.models import Build, TestRun, TestCaseRun

BASE_URL = "http://10.177.140.34:8080"
API_RESULTS_URL = f"{BASE_URL}/api/results"  # ← Твой основной эндпоинт из Swagger
API_REPORT_URL = f"{BASE_URL}/api/report"    # Для списка готовых отчётов (если нужно)

def extract_architecture(csv_content: str) -> str:
    reader = csv.DictReader(io.StringIO(csv_content))
    for row in list(reader)[:10]:
        suite = row.get("Suite") or row.get("Parent Suite") or ""
        if "." in suite:
            return suite.split(".", 1)[0].strip()
    return "Unknown Architecture"

class Command(BaseCommand):
    help = "Импорт всех прогонов через твой Swagger API (/api/results)"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Только тест')
        parser.add_argument('--limit', type=int, default=0, help='Ограничить количество')
        parser.add_argument('--use-reports', action='store_true', help='Использовать /api/report вместо /api/results')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        use_reports = options['use_reports']

        api_url = API_REPORT_URL if use_reports else API_RESULTS_URL
        self.stdout.write(f"Тянем список прогонов из: {api_url}")

        try:
            r = requests.get(api_url, timeout=20)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка API: {e}"))
            self.stdout.write(self.style.ERROR("Проверь, что Swagger API доступен. Попробуй --use-reports"))
            return

        # Парсим ответ (поддержка разных схем из Swagger)
        if isinstance(data, dict) and 'items' in data:
            reports = data['items']
        elif isinstance(data, list):
            reports = data
        elif isinstance(data, dict) and 'results' in data:
            reports = data['results']
        else:
            self.stdout.write(self.style.ERROR(f"Неизвестный формат ответа: {type(data)}"))
            return

        self.stdout.write(self.style.SUCCESS(f"УСПЕХ! Найдено {len(reports)} прогонов"))

        imported = skipped = failed = 0

        for idx, report in enumerate(reports[:limit or None]):
            # Адаптация под схему Swagger (uuid, name, created, uid и т.д.)
            uuid = report.get('uuid') or report.get('uid') or report.get('id')
            build_number = report.get('name') or report.get('title') or report.get('path') or str(uuid[:8])  # fallback
            timestamp = report.get('created') or report.get('timestamp') or report.get('date')

            if not uuid or not build_number:
                self.stdout.write(self.style.WARNING(f"Пропуск {idx+1}: нет uuid/имени"))
                continue

            # Парсинг даты
            try:
                if isinstance(timestamp, (int, float)):
                    build_date = datetime.fromtimestamp(timestamp / 1000).date()
                else:
                    build_date = datetime.now().date()
            except:
                build_date = datetime.now().date()

            if Build.objects.filter(build_number=build_number).exists():
                skipped += 1
                continue

            self.stdout.write(f"[{idx+1}/{len(reports)}] Импорт {build_number} (UUID: {uuid[:8]}...)")

            if dry_run:
                continue

            # Скачиваем suites.csv по UUID
            csv_url = f"{BASE_URL}/allure/reports/{uuid}/data/suites.csv"
            try:
                csv_r = requests.get(csv_url, timeout=40)
                csv_r.raise_for_status()
                csv_content = csv_r.text
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  CSV не скачан: {e}"))
                failed += 1
                continue

            architecture = extract_architecture(csv_content)

            with transaction.atomic():
                build, _ = Build.objects.get_or_create(build_number=build_number, defaults={'date': build_date})
                test_run = TestRun.objects.create(
                    build=build, architecture=architecture, run_date=build_date,
                    allure_report_url=f"{BASE_URL}/allure/reports/{uuid}/",
                    total_tests=0, passed_tests=0, failed_tests=0, skipped_tests=0
                )

                passed = failed_t = skipped_t = 0
                reader = csv.DictReader(io.StringIO(csv_content))
                for row in reader:
                    status = row.get('Status', '').lower()
                    name = row.get('Test Method') or row.get('Name', 'unknown')
                    TestCaseRun.objects.create(
                        test_run=test_run,
                        test_name=name.strip(),
                        status=status,
                        execution_date=build_date
                    )
                    if status == 'passed': passed += 1
                    elif status == 'failed': failed_t += 1
                    elif status == 'skipped': skipped_t += 1

                test_run.total_tests = passed + failed_t + skipped_t
                test_run.passed_tests = passed
                test_run.failed_tests = failed_t
                test_run.skipped_tests = skipped_t
                test_run.save()

                imported += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ {build_number} | {architecture} | {passed}p/{failed_t}f/{skipped_t}s"))

        self.stdout.write(self.style.SUCCESS(f"\nИТОГ: импортировано {imported}, пропущено {skipped}, ошибок {failed}"))