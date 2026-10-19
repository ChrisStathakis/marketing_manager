"""Validate the Instagram sessionid and, optionally, pull a post's comments.

    python manage.py instagram_check
    python manage.py instagram_check --url https://www.instagram.com/p/XXXX/ --limit 20

Useful before wiring anything in the UI: it tells you whether the stored cookie
still works and which account it belongs to.
"""
from django.core.management.base import BaseCommand, CommandError

from integrations.services import record_sync

from growth.instagram import InstagramError, InstagramNotConfigured, InstagramSessionInvalid
from growth.instagram_service import PROVIDER, get_client, resolve_post, sync_post


class Command(BaseCommand):
    help = "Check the Instagram session and optionally scrape a public post's comments."

    def add_arguments(self, parser):
        parser.add_argument("--url", help="A public post URL to fetch comments from.")
        parser.add_argument("--limit", type=int, default=20, help="Max comments to fetch (default 20).")

    def handle(self, *args, **options):
        try:
            client = get_client()
        except InstagramNotConfigured as exc:
            raise CommandError(str(exc))

        try:
            username = client.validate()
        except InstagramSessionInvalid as exc:
            record_sync(PROVIDER, error=str(exc))
            raise CommandError(str(exc))
        except InstagramError as exc:
            record_sync(PROVIDER, error=str(exc))
            raise CommandError(str(exc))
        record_sync(PROVIDER)
        self.stdout.write(self.style.SUCCESS(f"Session OK — logged in as @{username}"))

        url = options.get("url")
        if not url:
            return

        try:
            post, created = resolve_post(url)
        except ValueError as exc:
            raise CommandError(str(exc))
        self.stdout.write(f"Post {post.shortcode} ({'created' if created else 'already tracked'}).")

        try:
            result = sync_post(post, amount=options["limit"], client=client)
        except InstagramError as exc:
            record_sync(PROVIDER, error=str(exc))
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(result.summary()))
        for comment in post.comments.all()[:10]:
            self.stdout.write(f"  @{comment.author_username}: {comment.text[:60]}")
