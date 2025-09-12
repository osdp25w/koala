from django.db import models


class RentalActionOption(models.TextChoices):
    RENT = 'rent', 'Rent'
    RETURN = 'return', 'Return'
