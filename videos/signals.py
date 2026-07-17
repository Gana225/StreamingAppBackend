from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.postgres.search import SearchVector
from .models import Video

@receiver(post_save, sender=Video)
def update_video_search_vector(sender, instance, **kwargs):
    """
    Asynchronously or instantly computes search weights.
    Gives Title priority ('A') over Description ('B').
    """
    # Prevent infinite recursion loops by filtering down execution conditions
    if kwargs.get('update_fields') and 'search_vector' in kwargs.get('update_fields'):
        return

    Video.objects.filter(pk=instance.pk).update(
        search_vector=(
            SearchVector('title', weight='A') +
            SearchVector('description', weight='B')
        )
    )