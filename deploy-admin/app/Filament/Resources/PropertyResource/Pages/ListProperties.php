<?php

namespace App\Filament\Resources\PropertyResource\Pages;

use App\Filament\Resources\PropertyResource;
use Filament\Resources\Pages\ListRecords;

class ListProperties extends ListRecords
{
    protected static string $resource = PropertyResource::class;

    public function getHeading(): string|\Illuminate\Contracts\Support\Htmlable
    {
        $listingType = request()->query('listing_type');
        $propertyType = request()->query('property_type');

        $listingLabels = [
            'sale' => 'For Sale',
            'long_rent' => 'For Long-term Rent',
            'short_rent' => 'For Short-term Rent',
        ];

        $typeLabels = [
            'apartment' => 'Apartments', 'studio' => 'Studios', 'house' => 'Houses',
            'maisonette' => 'Maisonettes', 'townhouse' => 'Townhouses', 'penthouse' => 'Penthouses',
            'duplex' => 'Duplexes', 'bungalow' => 'Bungalows', 'cottage' => 'Cottages',
            'room' => 'Rooms', 'office' => 'Offices', 'shop' => 'Shops',
            'restaurant' => 'Restaurants', 'industrial' => 'Industrial', 'hotel' => 'Hotels',
            'business' => 'Business & Investment', 'land' => 'Land', 'building' => 'Buildings',
        ];

        if ($listingType && $propertyType) {
            return ($typeLabels[$propertyType] ?? ucfirst($propertyType)) . ' — ' . ($listingLabels[$listingType] ?? $listingType);
        }

        if ($listingType) {
            return 'Properties ' . ($listingLabels[$listingType] ?? $listingType);
        }

        return 'All Properties';
    }
}
