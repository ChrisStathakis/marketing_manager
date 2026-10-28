from django.core.management.base import BaseCommand

from growth.playbooks import seed_top8_playbook


class Command(BaseCommand):
    help = "Seed the editable Top 8 launch playbook and its hashtag banks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Replace the slots of an existing seeded playbook (custom playbooks are untouched).",
        )

    def handle(self, *args, **options):
        playbook, created = seed_top8_playbook(force=options["force"])
        action = "Created" if created else ("Refreshed" if options["force"] else "Already present")
        self.stdout.write(
            self.style.SUCCESS(
                f"{action}: {playbook.name} ({playbook.slots.count()} slots). "
                "Run it from Growth > Playbooks, or POST /api/playbooks/{id}/run/."
            )
        )
