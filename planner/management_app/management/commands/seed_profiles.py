import csv
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


EXPECTED_FIELDS = ("username", "password", "first_name", "last_name", "role", "tech")


class Command(BaseCommand):
    help = (
        "Create or update 19 development profiles from "
        "authentication/credentials.txt."
    )

    def handle(self, *args, **options):
        credentials_path = settings.BASE_DIR / "authentication" / "credentials.txt"
        profiles = self._read_profiles(credentials_path)
        user_model = get_user_model()
        valid_roles = {value for value, _ in user_model._meta.get_field("role").choices}
        valid_techs = {
            value for value, _ in user_model._meta.get_field("tech").choices
        }

        for profile in profiles:
            if profile["role"] not in valid_roles:
                raise CommandError(
                    f"Invalid role {profile['role']!r} for {profile['username']}."
                )
            if profile["tech"] and profile["tech"] not in valid_techs:
                raise CommandError(
                    f"Invalid tech {profile['tech']!r} for {profile['username']}."
                )

        created_count = 0
        with transaction.atomic():
            for profile_data in profiles:
                profile = profile_data.copy()
                password = profile.pop("password")
                username = profile["username"]
                profile["tech"] = profile["tech"] or None

                user, created = user_model.objects.get_or_create(
                    username=username,
                    defaults=profile,
                )
                for field, value in profile.items():
                    setattr(user, field, value)
                user.set_password(password)
                user.save()
                created_count += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(profiles)} profiles "
                f"({created_count} created, {len(profiles) - created_count} updated)."
            )
        )

    @staticmethod
    def _read_profiles(credentials_path: Path):
        try:
            with credentials_path.open(encoding="utf-8", newline="") as credentials_file:
                reader = csv.DictReader(
                    line
                    for line in credentials_file
                    if not line.lstrip().startswith("#")
                )
                if tuple(reader.fieldnames or ()) != EXPECTED_FIELDS:
                    raise CommandError(
                        f"{credentials_path} must have these columns: "
                        f"{', '.join(EXPECTED_FIELDS)}."
                    )

                profiles = list(reader)
        except OSError as exc:
            raise CommandError(
                f"Could not read credentials file {credentials_path}: {exc}"
            ) from exc

        if len(profiles) != 19:
            raise CommandError(
                f"{credentials_path} must contain exactly 19 profile rows; "
                f"found {len(profiles)}."
            )

        usernames = []
        for line_number, profile in enumerate(profiles, start=3):
            if None in profile or any(
                not isinstance(profile.get(field), str)
                or not profile[field].strip()
                for field in EXPECTED_FIELDS
                if field not in ("tech",)
            ):
                raise CommandError(
                    f"Invalid or incomplete credentials row at line {line_number}."
                )
            usernames.append(profile["username"])

        if len(usernames) != len(set(usernames)):
            raise CommandError("The credentials file contains duplicate usernames.")

        return profiles
