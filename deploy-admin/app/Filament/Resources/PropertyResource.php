<?php

namespace App\Filament\Resources;

use App\Filament\Resources\PropertyResource\Pages;
use App\Models\Property;
use Filament\Forms\Components\TextInput;
use Filament\Forms\Components\RichEditor;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\Toggle;
use Filament\Schemas\Schema;
use Filament\Schemas\Components\Tabs;
use Filament\Schemas\Components\Tabs\Tab;
use Filament\Resources\Resource;
use Filament\Tables;
use Filament\Tables\Table;
use Filament\Actions\EditAction;
use Filament\Actions\DeleteAction;
use Filament\Actions\DeleteBulkAction;
use Filament\Navigation\NavigationItem;
use Illuminate\Database\Eloquent\Builder;

class PropertyResource extends Resource
{
    protected static ?string $model = Property::class;
    protected static ?string $navigationIcon = 'heroicon-o-building-office-2';
    protected static ?string $navigationGroup = 'Property';

    public static function getNavigationItems(): array
    {
        $counts = Property::selectRaw('listing_type, property_type, count(*) as total')
            ->groupBy('listing_type', 'property_type')
            ->get()
            ->keyBy(fn ($item) => $item->listing_type . '|' . $item->property_type)
            ->map(fn ($item) => $item->total);

        $listingTotals = Property::selectRaw('listing_type, count(*) as total')
            ->groupBy('listing_type')
            ->pluck('total', 'listing_type');

        $typeLabels = [
            'apartment' => 'Apartment', 'studio' => 'Studio', 'house' => 'House',
            'maisonette' => 'Maisonette', 'townhouse' => 'Townhouse', 'penthouse' => 'Penthouse',
            'duplex' => 'Duplex', 'bungalow' => 'Bungalow', 'cottage' => 'Cottage',
            'room' => 'Room', 'office' => 'Office', 'shop' => 'Shop',
            'restaurant' => 'Restaurant', 'industrial' => 'Industrial', 'hotel' => 'Hotel',
            'business' => 'Business & Investment', 'land' => 'Land', 'building' => 'Building',
        ];

        $categories = [
            'sale' => [
                'label' => 'For Sale',
                'types' => ['apartment', 'studio', 'house', 'maisonette', 'townhouse', 'penthouse', 'duplex', 'bungalow', 'cottage', 'office', 'shop', 'restaurant', 'industrial', 'hotel', 'business', 'land', 'building'],
            ],
            'long_rent' => [
                'label' => 'For Long-term Rent',
                'types' => ['apartment', 'studio', 'house', 'maisonette', 'room', 'townhouse', 'penthouse', 'duplex', 'bungalow', 'cottage', 'office', 'shop', 'restaurant', 'hotel', 'industrial'],
            ],
            'short_rent' => [
                'label' => 'For Short-term Rent',
                'types' => ['apartment', 'studio', 'house', 'maisonette', 'room', 'townhouse', 'penthouse', 'duplex', 'bungalow', 'cottage'],
            ],
        ];

        $items = [];
        $baseUrl = static::getUrl('index');
        $createUrl = static::getUrl('create');
        $sort = 0;

        $allCount = Property::count();
        $items[] = NavigationItem::make("All Properties ({$allCount})")
            ->group('Property')
            ->icon('heroicon-o-building-office-2')
            ->url($baseUrl)
            ->isActiveWhen(fn () => request()->routeIs(static::getRouteBaseName() . '.index') && !request()->query('listing_type'))
            ->sort($sort++);

        $items[] = NavigationItem::make('+ Add Property')
            ->group('Property')
            ->icon('heroicon-o-plus-circle')
            ->url($createUrl)
            ->isActiveWhen(fn () => request()->routeIs(static::getRouteBaseName() . '.create'))
            ->sort($sort++);

        foreach ($categories as $listingType => $category) {
            $lt = $listingType;
            $catTotal = $listingTotals->get($listingType, 0);

            $items[] = NavigationItem::make($category['label'] . " ({$catTotal})")
                ->group('Property')
                ->icon(match ($listingType) {
                    'sale' => 'heroicon-o-banknotes',
                    'long_rent' => 'heroicon-o-key',
                    'short_rent' => 'heroicon-o-clock',
                    default => 'heroicon-o-folder',
                })
                ->url($baseUrl . '?' . http_build_query(['listing_type' => $lt]))
                ->isActiveWhen(fn () => request()->query('listing_type') === $lt && !request()->query('property_type'))
                ->sort($sort++);

            foreach ($category['types'] as $propertyType) {
                $count = $counts->get("{$listingType}|{$propertyType}", 0);
                $label = '· ' . ($typeLabels[$propertyType] ?? ucfirst($propertyType)) . " ({$count})";

                $pt = $propertyType;

                $items[] = NavigationItem::make($label)
                    ->group('Property')
                    ->url($baseUrl . '?' . http_build_query(['listing_type' => $lt, 'property_type' => $pt]))
                    ->isActiveWhen(fn () => request()->query('listing_type') === $lt && request()->query('property_type') === $pt)
                    ->sort($sort++);
            }
        }

        return $items;
    }

    public static function form(Schema $schema): Schema
    {
        return $schema->components([
            Tabs::make('Property')->tabs([
                Tab::make('Basic Info')->schema([
                    TextInput::make('title')->required()->maxLength(255)->columnSpanFull(),
                    RichEditor::make('description')->columnSpanFull(),
                    Select::make('listing_type')
                        ->options([
                            'sale' => 'For Sale',
                            'long_rent' => 'For Long-term Rent',
                            'short_rent' => 'For Short-term Rent',
                        ])->required(),
                    Select::make('property_type')
                        ->options([
                            'apartment' => 'Apartment', 'studio' => 'Studio', 'house' => 'House',
                            'maisonette' => 'Maisonette', 'townhouse' => 'Townhouse', 'penthouse' => 'Penthouse',
                            'duplex' => 'Duplex', 'bungalow' => 'Bungalow', 'cottage' => 'Cottage',
                            'room' => 'Room', 'office' => 'Office', 'shop' => 'Shop',
                            'restaurant' => 'Restaurant', 'industrial' => 'Industrial', 'hotel' => 'Hotel',
                            'business' => 'Business & Investment', 'land' => 'Land', 'building' => 'Building',
                        ])->required(),
                    TextInput::make('sub_type')->placeholder('e.g. Detached, Semi-detached'),
                    Select::make('status')
                        ->options([
                            'active' => 'Active', 'inactive' => 'Inactive',
                            'pending' => 'Pending', 'sold' => 'Sold',
                        ])->default('active')->required(),
                ])->columns(2),

                Tab::make('Price')->schema([
                    TextInput::make('price')->required()->numeric()->prefix('£'),
                    TextInput::make('old_price')->numeric()->prefix('£'),
                    Select::make('currency')
                        ->options(['GBP' => '£ GBP', 'EUR' => '€ EUR', 'USD' => '$ USD'])
                        ->default('GBP'),
                    Toggle::make('negotiable')->label('Price negotiable'),
                ])->columns(2),

                Tab::make('Location')->schema([
                    TextInput::make('country')->default('United Kingdom'),
                    TextInput::make('city')->required(),
                    TextInput::make('district'),
                    TextInput::make('postal_code'),
                    TextInput::make('address')->columnSpanFull(),
                    TextInput::make('latitude')->numeric(),
                    TextInput::make('longitude')->numeric(),
                ])->columns(2),

                Tab::make('Specifications')->schema([
                    TextInput::make('bedrooms')->numeric()->minValue(0)->maxValue(50),
                    TextInput::make('bathrooms')->numeric()->minValue(0)->maxValue(50),
                    TextInput::make('covered_area')->numeric()->suffix('m²'),
                    TextInput::make('plot_area')->numeric()->suffix('m²'),
                    TextInput::make('construction_year')->numeric()
                        ->minValue(1900)->maxValue(2030),
                    Select::make('condition')
                        ->options([
                            'new' => 'New Build', 'resale' => 'Resale',
                            'under_construction' => 'Under Construction',
                        ]),
                    Select::make('energy_efficiency')
                        ->options([
                            'A+' => 'A+', 'A' => 'A', 'B' => 'B', 'C' => 'C',
                            'D' => 'D', 'E' => 'E', 'F' => 'F', 'G' => 'G',
                        ]),
                ])->columns(2),

                Tab::make('Features')->schema([
                    Toggle::make('furnished'),
                    Toggle::make('air_conditioning')->label('Air Conditioning'),
                    Toggle::make('parking'),
                    Toggle::make('pool'),
                    Toggle::make('garden'),
                    Toggle::make('veranda'),
                    Toggle::make('gym'),
                    Toggle::make('elevator'),
                    Toggle::make('security'),
                    Toggle::make('solar_panels')->label('Solar Panels'),
                ])->columns(3),

                Tab::make('Contact & Media')->schema([
                    TextInput::make('seller_name'),
                    TextInput::make('seller_phone')->tel(),
                    TextInput::make('seller_whatsapp'),
                    TextInput::make('seller_email')->email(),
                    TextInput::make('video_url')->label('YouTube Video URL')->url(),
                ])->columns(2),

                Tab::make('Promotion')->schema([
                    Toggle::make('is_vip')->label('VIP'),
                    Toggle::make('is_pro')->label('PRO'),
                    Toggle::make('is_top')->label('TOP'),
                ])->columns(3),
            ])->columnSpanFull(),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->modifyQueryUsing(function (Builder $query) {
                if ($listingType = request()->query('listing_type')) {
                    $query->where('listing_type', $listingType);
                }
                if ($propertyType = request()->query('property_type')) {
                    $query->where('property_type', $propertyType);
                }
            })
            ->columns([
                Tables\Columns\TextColumn::make('id')->sortable(),
                Tables\Columns\TextColumn::make('title')->searchable()->limit(30),
                Tables\Columns\TextColumn::make('listing_type')->badge()
                    ->color(fn (string $state): string => match ($state) {
                        'sale' => 'success',
                        'long_rent' => 'info',
                        'short_rent' => 'warning',
                        default => 'gray',
                    }),
                Tables\Columns\TextColumn::make('property_type')->badge(),
                Tables\Columns\TextColumn::make('city')->searchable(),
                Tables\Columns\TextColumn::make('price')->money('GBP')->sortable(),
                Tables\Columns\TextColumn::make('bedrooms')->sortable(),
                Tables\Columns\TextColumn::make('status')->badge()
                    ->color(fn (string $state): string => match ($state) {
                        'active' => 'success',
                        'pending' => 'warning',
                        'sold' => 'danger',
                        default => 'gray',
                    }),
                Tables\Columns\IconColumn::make('is_vip')->boolean()->label('VIP'),
                Tables\Columns\TextColumn::make('created_at')->dateTime()->sortable(),
            ])
            ->filters([
                Tables\Filters\SelectFilter::make('listing_type')
                    ->options([
                        'sale' => 'For Sale',
                        'long_rent' => 'For Long-term Rent',
                        'short_rent' => 'For Short-term Rent',
                    ]),
                Tables\Filters\SelectFilter::make('property_type')
                    ->options([
                        'apartment' => 'Apartment', 'studio' => 'Studio', 'house' => 'House',
                        'maisonette' => 'Maisonette', 'townhouse' => 'Townhouse', 'penthouse' => 'Penthouse',
                        'duplex' => 'Duplex', 'bungalow' => 'Bungalow', 'cottage' => 'Cottage',
                        'room' => 'Room', 'office' => 'Office', 'shop' => 'Shop',
                        'restaurant' => 'Restaurant', 'industrial' => 'Industrial', 'hotel' => 'Hotel',
                        'business' => 'Business & Investment', 'land' => 'Land', 'building' => 'Building',
                    ]),
                Tables\Filters\SelectFilter::make('status')
                    ->options([
                        'active' => 'Active', 'inactive' => 'Inactive',
                        'pending' => 'Pending', 'sold' => 'Sold',
                    ]),
            ])
            ->actions([
                EditAction::make(),
                DeleteAction::make(),
            ])
            ->bulkActions([
                DeleteBulkAction::make(),
            ])
            ->defaultSort('created_at', 'desc');
    }

    public static function getPages(): array
    {
        return [
            'index' => Pages\ListProperties::route('/'),
            'create' => Pages\CreateProperty::route('/create'),
            'edit' => Pages\EditProperty::route('/{record}/edit'),
        ];
    }
}
