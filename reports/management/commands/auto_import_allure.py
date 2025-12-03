# reports/management/commands/auto_import_allure.py

import csv
import io
import requests
from datetime import datetime
from dateutil import parser as dateutil_parser

from django.core.management.base import BaseCommand
from django.db import transaction

from reports.models import Build, TestRun, TestCaseRun


BASE_URL = "http://10.177.140.34:8080"
API_REPORT_URL = f"{BASE_URL}/api/report"


class Command(BaseCommand):
    help = "Универсальный импорт Allure: поддерживает suites.csv и data_suites.csv"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=0)

    def download_csv(self, uuid):
        """Пробует оба пути и возвращает (content, source)"""
        urls = [
            f"{BASE_URL}/allure/reports/{uuid}/data/suites.csv",      # новый формат
            f"{BASE_URL}/allure/reports/{uuid}/data_suites.csv",       # старый формат
        ]
        for url in urls:
            try:
                r = requests.get(url, timeout=40)
                if r.status_code == 200:
                    source = url.split('/')[-1]  # suites.csv или data_suites.csv
                    self.stdout.write(self.style.SUCCESS(f"  CSV найден: {source}"))
                    return r.text, source
            except Exception as e:
                continue
        self.stdout.write(self.style.WARNING("  CSV не найден ни по одному пути"))
        return None, None

    def get_build_date_from_csv(self, csv_content, source):
        if not csv_content:
            return None

        reader = csv.DictReader(io.StringIO(csv_content))
        dates = []

        for row in reader:
            stop = (
                row.get('Stop Time') or row.get('STOP TIME') or
                row.get('Start Time') or row.get('START TIME')
            )
            if stop and stop.strip() and stop.lower() not in ('null', ''):
                try:
                    dt = dateutil_parser.parse(stop, tzinfos={"MSK": 3*3600})
                    dates.append(dt.date())
                except:
                    continue

        return max(dates) if dates else Null   # ← вот эта строка должна быть именно такой!



    def get_type_and_arch(self, name):
        n = name.upper()
        if n.startswith('SMK-MOB-T17'):    return 'Mobile 17', 'Mobile 17'
        if n.startswith('SMK-MOB-T18'):    return 'Mobile 18', 'Mobile 18'
        if n.startswith('SMK-RUN18-'):  return 'ALSE 18', 'ALSE 18'
        if n.startswith('SMK-RUN17-'):  return 'ALSE 17', 'ALSE 17'
        if n.startswith('SMK-INIT18-'): return 'Init18', 'Init18'
        if n.startswith('SMK-BNCH-'):   return 'Benchmark', 'Benchmark'
        return 'Other', 'Other'

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']

        self.stdout.write("Получаем список отчётов...")
        resp = requests.get(API_REPORT_URL, timeout=30)
        resp.raise_for_status()
        reports = resp.json() if isinstance(resp.json(), list) else resp.json().get('items', [])

        self.stdout.write(self.style.SUCCESS(f"Найдено отчётов: {len(reports)}"))

        imported = skipped = 0

        for idx, rep in enumerate(reports[:limit or None]):
            uuid = rep.get('uuid')
            build_number = rep.get('path') or rep.get('name') or 'unknown'

            if not uuid or not build_number:
                continue

            self.stdout.write(f"[{idx+1}/{len(reports)}] {build_number} (uuid={uuid[:8]})")

            # Скачиваем CSV — любой из двух форматов
            csv_content, csv_source = self.download_csv(uuid)
            if not csv_content:
                csv_content = ""  # всё равно создадим билд с 0 тестов

            build_date = self.get_build_date_from_csv(csv_content, csv_source)
            build_type, architecture = self.get_type_and_arch(build_number)


            


            if Build.objects.filter(uuid=uuid).exists():
                self.stdout.write(self.style.NOTICE("  Уже в базе — пропускаем"))
                skipped += 1
                continue

            if dry_run:
                imported += 1
                continue

            try:
                with transaction.atomic():

                    build = Build.objects.create(
                        build_number=str(build_number)[:200],
                        date=build_date,
                        build_type=build_type,
                        uuid = uuid
                    )

                    test_run = TestRun.objects.create(
                        build=build,
                        architecture=architecture,
                        run_date=build_date,
                        allure_report_url=f"{BASE_URL}/allure/reports/{uuid}/",
                        total_tests=0, passed_tests=0, failed_tests=0, skipped_tests=0,
                    )

                    if csv_content:
                        reader = csv.DictReader(io.StringIO(csv_content))
                        p = f = s = 0
                        for row in reader:
                            status_raw = row.get('Status') or row.get('STATUS') or 'skipped'
                            status = status_raw.lower()

                            name = (
                                row.get('Test Method') or
                                row.get('Name') or
                                row.get('TEST METHOD') or
                                row.get('NAME') or
                                'unknown'
                            ).strip()[:500]

                            if not name:
                                name = 'empty_name'

                            if status in ['passed', 'pass']: status = 'passed'; p += 1
                            elif status in ['failed', 'failure', 'broken']: status = 'failed'; f += 1
                            else: status = 'skipped'; s += 1

                            TestCaseRun.objects.create(
                                test_run=test_run,
                                test_name=name,
                                status=status,
                                execution_date=build_date,
                                architecture=architecture,
                            )

                        test_run.total_tests = p + f + s
                        test_run.passed_tests = p
                        test_run.failed_tests = f
                        test_run.skipped_tests = s
                        test_run.save()

                    imported += 1
                    self.stdout.write(self.style.SUCCESS(f"  Импортирован! {p}p/{f}f/{s}s"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ОШИБКА при сохранении {build_number}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nГОТОВО! Импортировано: {imported} | Пропущено: {skipped}"))
