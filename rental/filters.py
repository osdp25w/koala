import django_filters

from .models import BikeRental


class BikeRentalFilter(django_filters.FilterSet):
    email = django_filters.CharFilter(
        field_name='member__user__email', lookup_expr='icontains'
    )
    rental_status = django_filters.ChoiceFilter(
        choices=BikeRental.RentalStatusOptions.choices
    )
    bike_id = django_filters.CharFilter(
        field_name='bike__bike_id', lookup_expr='icontains'
    )

    class Meta:
        model = BikeRental
        fields = ['email', 'rental_status', 'bike_id']
