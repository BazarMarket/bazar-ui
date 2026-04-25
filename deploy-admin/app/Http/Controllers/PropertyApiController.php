<?php

namespace App\Http\Controllers;

use App\Models\Property;
use App\Models\Customer;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

class PropertyApiController extends Controller
{
    public function store(Request $request)
    {
        $validated = $request->validate([
            'title' => 'required|string|max:255',
            'description' => 'nullable|string',
            'listing_type' => 'required|in:sale,long_rent,short_rent,rent',
            'property_type' => 'required|string',
            'sub_type' => 'nullable|string',
            'building_type' => 'nullable|string',
            'parking_type' => 'nullable|string',
            'furnishing_type' => 'nullable|string',
            'ac_type' => 'nullable|string',
            'price' => 'required|numeric|min:0',
            'currency' => 'required|string|max:3',
            'negotiable' => 'nullable|boolean',
            'country' => 'required|string|max:255',
            'city' => 'required|string|max:255',
            'district' => 'nullable|string|max:255',
            'region' => 'nullable|string|max:255',
            'postal_code' => 'nullable|string|max:20',
            'address' => 'nullable|string|max:255',
            'latitude' => 'nullable|numeric',
            'longitude' => 'nullable|numeric',
            'exact_latitude' => 'nullable|numeric',
            'exact_longitude' => 'nullable|numeric',
            'bedrooms' => 'nullable|integer|min:0',
            'bathrooms' => 'nullable|integer|min:0',
            'covered_area' => 'nullable|integer|min:0',
            'plot_area' => 'nullable|integer|min:0',
            'floor' => 'nullable|string',
            'construction_year' => 'nullable|integer|min:1800|max:2030',
            'condition' => 'nullable|in:new,resale,under_construction',
            'energy_efficiency' => 'nullable|string|max:5',
            'online_viewing'    => 'nullable|string|max:50',
            'registration_block'   => 'nullable|string|max:100',
            'registration_number'  => 'nullable|string|max:100',
            'furnished' => 'nullable|boolean',
            'air_conditioning' => 'nullable|boolean',
            'parking' => 'nullable|boolean',
            'pool' => 'nullable|boolean',
            'garden' => 'nullable|boolean',
            'veranda' => 'nullable|boolean',
            'gym' => 'nullable|boolean',
            'elevator' => 'nullable|boolean',
            'security' => 'nullable|boolean',
            'solar_panels' => 'nullable|boolean',
            'balcony' => 'nullable|boolean',
            'terrace' => 'nullable|boolean',
            'central_heating' => 'nullable|boolean',
            'storage_room' => 'nullable|boolean',
            'seller_name' => 'required|string|max:255',
            'seller_phone' => 'required|string|max:50',
            'seller_email' => 'nullable|email|max:255',
            'has_whatsapp' => 'nullable|boolean',
            'has_telegram' => 'nullable|boolean',
            'has_viber' => 'nullable|boolean',
            'has_email' => 'nullable|boolean',
            'video_url' => 'nullable|url|max:255',
            'images' => 'nullable|array',
            'images.*' => 'image|mimes:jpg,jpeg,png,webp|max:5120',
            'car_make' => 'nullable|string|max:100',
            'car_model' => 'nullable|string|max:100',
            'car_year' => 'nullable|integer|min:1900|max:2030',
            'mileage' => 'nullable|integer|min:0',
            'fuel_type' => 'nullable|string|max:50',
            'transmission' => 'nullable|string|max:50',
            'body_type' => 'nullable|string|max:50',
            'colour' => 'nullable|string|max:50',
            'doors' => 'nullable|integer|min:1|max:10',
            'seats' => 'nullable|integer|min:1|max:20',
            'drive_type' => 'nullable|string|max:50',
            'steering_side' => 'nullable|string|max:20',
            'engine_size' => 'nullable|string|max:20',
            'previous_owners' => 'nullable|integer|min:0',
            'service_history' => 'nullable|string|max:50',
            'mot_status' => 'nullable|string|max:50',
            'phone_brand' => 'nullable|string|max:100',
            'phone_model' => 'nullable|string|max:100',
            'phone_storage' => 'nullable|string|max:20',
            'phone_ram' => 'nullable|string|max:20',
            'sim_type' => 'nullable|string|max:50',
            'network' => 'nullable|string|max:50',
            'battery_health' => 'nullable|string|max:20',
            'operating_system' => 'nullable|string|max:30',
            'unlock_status' => 'nullable|string|max:30',
            'warranty' => 'nullable|string|max:50',
            'original_box' => 'nullable|string|max:10',
            'charger_included' => 'nullable|string|max:10',
            'seller_type' => 'nullable|string|max:30',
        ]);

        // Plan-based photo limit
        $firebaseUid = $request->input('firebase_uid');
        $photoLimit = 10; // free default
        if ($firebaseUid) {
            $cust = \App\Models\Customer::where('firebase_uid', $firebaseUid)->first();
            if ($cust) {
                $custPlan = strtolower($cust->bazar_plan ?? $cust->plan ?? 'free');
                if ($custPlan === 'vip') $photoLimit = 50;
                elseif ($custPlan === 'pro') $photoLimit = 20;
            }
        }
        $imagePaths = [];
        if ($request->hasFile('images')) {
            $uploaded = 0;
            foreach ($request->file('images') as $image) {
                if ($uploaded >= $photoLimit) break;
                $filename = Str::uuid() . '.' . $image->getClientOriginalExtension();
                $image->storeAs('properties', $filename, 'public');
                $imagePaths[] = 'properties/' . $filename;
                $uploaded++;
            }
        }

        $property = Property::create([
            'firebase_uid'     => $request->input('firebase_uid'),
            'title'            => $validated['title'],
            'description'      => $validated['description'] ?? null,
            'listing_type'     => $validated['listing_type'],
            'property_type'    => $validated['property_type'],
            'sub_type'         => $validated['sub_type'] ?? null,
            'building_type'    => $validated['building_type'] ?? null,
            'parking_type'     => $validated['parking_type'] ?? null,
            'furnishing_type'  => $validated['furnishing_type'] ?? null,
            'ac_type'          => $validated['ac_type'] ?? null,
            'price'            => $validated['price'],
            'currency'         => $validated['currency'],
            'negotiable'       => $validated['negotiable'] ?? false,
            'country'          => $validated['country'],
            'city'             => $validated['city'],
            'district'         => $validated['district'] ?? null,
            'region'           => $validated['region'] ?? null,
            'postal_code'      => $validated['postal_code'] ?? null,
            'address'          => $validated['address'] ?? null,
            'latitude'         => $validated['latitude'] ?? null,
            'longitude'        => $validated['longitude'] ?? null,
            'exact_latitude'   => $validated['exact_latitude'] ?? null,
            'exact_longitude'  => $validated['exact_longitude'] ?? null,
            'bedrooms'         => $validated['bedrooms'] ?? null,
            'bathrooms'        => $validated['bathrooms'] ?? null,
            'covered_area'     => $validated['covered_area'] ?? null,
            'plot_area'        => $validated['plot_area'] ?? null,
            'floor'            => $validated['floor'] ?? null,
            'construction_year'=> $validated['construction_year'] ?? null,
            'condition'        => $validated['condition'] ?? null,
            'energy_efficiency'=> $validated['energy_efficiency'] ?? null,
            'online_viewing'   => $validated['online_viewing'] ?? null,
            'registration_block'  => $validated['registration_block'] ?? null,
            'registration_number' => $validated['registration_number'] ?? null,
            'furnished'        => $validated['furnished'] ?? false,
            'air_conditioning' => $validated['air_conditioning'] ?? false,
            'parking'          => $validated['parking'] ?? false,
            'pool'             => $validated['pool'] ?? false,
            'garden'           => $validated['garden'] ?? false,
            'veranda'          => $validated['veranda'] ?? false,
            'gym'              => $validated['gym'] ?? false,
            'elevator'         => $validated['elevator'] ?? false,
            'security'         => $validated['security'] ?? false,
            'solar_panels'     => $validated['solar_panels'] ?? false,
            'balcony'          => $validated['balcony'] ?? false,
            'terrace'          => $validated['terrace'] ?? false,
            'central_heating'  => $validated['central_heating'] ?? false,
            'storage_room'     => $validated['storage_room'] ?? false,
            'seller_name'      => $validated['seller_name'],
            'seller_phone'     => $validated['seller_phone'],
            'seller_email'     => $validated['seller_email'] ?? null,
            'seller_whatsapp'  => ($validated['has_whatsapp'] ?? false) ? $validated['seller_phone'] : null,
            'has_telegram'     => $validated['has_telegram'] ?? false,
            'has_viber'        => $validated['has_viber'] ?? false,
            'has_email'        => $validated['has_email'] ?? false,
            'video_url'        => $validated['video_url'] ?? null,
            'images'           => $imagePaths ?: null,
            'status'           => (
                $request->header('X-Bazar-Moderation') === 'pending' &&
                in_array($request->ip(), ['127.0.0.1', '::1', '49.13.231.137'])
                ? 'pending' : 'active'
            ),
            'car_make'         => $validated['car_make'] ?? null,
            'car_model'        => $validated['car_model'] ?? null,
            'car_year'         => $validated['car_year'] ?? null,
            'mileage'          => $validated['mileage'] ?? null,
            'fuel_type'        => $validated['fuel_type'] ?? null,
            'transmission'     => $validated['transmission'] ?? null,
            'body_type'        => $validated['body_type'] ?? null,
            'colour'           => $validated['colour'] ?? null,
            'doors'            => $validated['doors'] ?? null,
            'seats'            => $validated['seats'] ?? null,
            'drive_type'       => $validated['drive_type'] ?? null,
            'steering_side'    => $validated['steering_side'] ?? null,
            'engine_size'      => $validated['engine_size'] ?? null,
            'previous_owners'  => $validated['previous_owners'] ?? null,
            'service_history'  => $validated['service_history'] ?? null,
            'mot_status'       => $validated['mot_status'] ?? null,
            'phone_brand'      => $validated['phone_brand'] ?? null,
            'phone_model'      => $validated['phone_model'] ?? null,
            'phone_storage'    => $validated['phone_storage'] ?? null,
            'phone_ram'        => $validated['phone_ram'] ?? null,
            'sim_type'         => $validated['sim_type'] ?? null,
            'network'          => $validated['network'] ?? null,
            'battery_health'   => $validated['battery_health'] ?? null,
            'operating_system' => $validated['operating_system'] ?? null,
            'unlock_status'    => $validated['unlock_status'] ?? null,
            'warranty'         => $validated['warranty'] ?? null,
            'original_box'     => $validated['original_box'] ?? null,
            'charger_included' => $validated['charger_included'] ?? null,
            'seller_type'      => $validated['seller_type'] ?? null,
        ]);

        // Auto-create or update customer record from seller info
        $firebaseUid = $request->input('firebase_uid');
        if ($firebaseUid && !empty($validated['seller_name']) && !empty($validated['seller_phone'])) {
            \App\Models\Customer::updateOrCreate(
                ['firebase_uid' => $firebaseUid],
                [
                    'name'  => $validated['seller_name'],
                    'phone' => $validated['seller_phone'],
                    'gender' => 'male',
                    'plan'  => 'free',
                ]
            );
        }

        return response()->json([
            'success'     => true,
            'property_id' => $property->id,
            'status'      => $property->status,
        ], 201);
    }

    public function show($id)
    {
        $property = Property::findOrFail($id);

        $imageUrls = [];
        if (!empty($property->images)) {
            foreach ($property->images as $path) {
                $imageUrls[] = Storage::disk('public')->url($path);
            }
        }

        $mapQuery = implode(', ', array_filter([
            $property->address,
            $property->district,
            $property->city,
            $property->country,
        ]));

        return response()->json([
            'id'                => $property->id,
            'title'             => $property->title,
            'description'       => $property->description,
            'listing_type'      => $property->listing_type,
            'property_type'     => $property->property_type,
            'sub_type'          => $property->sub_type,
            'price'             => $property->price,
            'old_price'         => $property->old_price,
            'currency'          => $property->currency,
            'negotiable'        => (bool)$property->negotiable,
            'country'           => $property->country,
            'city'              => $property->city,
            'district'          => $property->district,
            'region'            => $property->region,
            'postal_code'       => $property->postal_code,
            'address'           => $property->address,
            'latitude'          => $property->latitude,
            'longitude'         => $property->longitude,
            'exact_latitude'    => $property->exact_latitude,
            'exact_longitude'   => $property->exact_longitude,
            'bedrooms'          => $property->bedrooms,
            'bathrooms'         => $property->bathrooms,
            'covered_area'      => $property->covered_area,
            'plot_area'         => $property->plot_area,
            'construction_year' => $property->construction_year,
            'condition'         => $property->condition,
            'energy_efficiency'    => $property->energy_efficiency,
            'online_viewing'       => $property->online_viewing,
            'registration_block'   => $property->registration_block,
            'registration_number'  => $property->registration_number,
            'furnished'         => (bool)$property->furnished,
            'air_conditioning'  => (bool)$property->air_conditioning,
            'parking'           => (bool)$property->parking,
            'parking_type'      => $property->parking_type,
            'pool'              => (bool)$property->pool,
            'garden'            => (bool)$property->garden,
            'veranda'           => (bool)$property->veranda,
            'security'          => (bool)$property->security,
            'solar_panels'      => (bool)$property->solar_panels,
            'balcony'           => (bool)$property->balcony,
            'terrace'           => (bool)$property->terrace,
            'central_heating'   => (bool)$property->central_heating,
            'storage_room'      => (bool)$property->storage_room,
            'building_type'     => $property->building_type,
            'furnishing_type'   => $property->furnishing_type,
            'ac_type'           => $property->ac_type,
            'floor'             => $property->floor,
            'gym'               => (bool)$property->gym,
            'is_vip'            => (bool)$property->is_vip,
            'is_pro'            => (bool)$property->is_pro,
            'seller_name'        => $property->seller_name,
            'seller_firebase_uid' => $property->firebase_uid,
            'seller_phone'      => $property->seller_phone,
            'elevator'         => (bool)$property->elevator,
            'has_whatsapp'      => !empty($property->seller_whatsapp),
            'has_telegram'      => (bool)$property->has_telegram,
            'has_viber'         => (bool)$property->has_viber,
            'has_email'         => (bool)$property->has_email,
            'seller_registered' => optional($property->created_at)->toDateString(),
            'image'             => !empty($imageUrls) ? $imageUrls[0] : null,
            'images'            => $imageUrls,
            'map_query'         => $mapQuery,
            'status'            => $property->status,
            'car_make'          => $property->car_make,
            'car_model'         => $property->car_model,
            'car_year'          => $property->car_year,
            'mileage'           => $property->mileage,
            'fuel_type'         => $property->fuel_type,
            'transmission'      => $property->transmission,
            'body_type'         => $property->body_type,
            'colour'            => $property->colour,
            'doors'             => $property->doors,
            'seats'             => $property->seats,
            'drive_type'        => $property->drive_type,
            'steering_side'     => $property->steering_side,
            'engine_size'       => $property->engine_size,
            'previous_owners'   => $property->previous_owners,
            'service_history'   => $property->service_history,
            'mot_status'        => $property->mot_status,
            'phone_brand'       => $property->phone_brand,
            'phone_model'       => $property->phone_model,
            'phone_storage'     => $property->phone_storage,
            'phone_ram'         => $property->phone_ram,
            'sim_type'          => $property->sim_type,
            'network'           => $property->network,
            'battery_health'    => $property->battery_health,
            'operating_system'  => $property->operating_system,
            'unlock_status'     => $property->unlock_status,
            'warranty'          => $property->warranty,
            'original_box'      => $property->original_box,
            'charger_included'  => $property->charger_included,
            'video_url'         => $property->video_url,
            'seller_type'       => $property->seller_type,
            'created_at'        => optional($property->created_at)->toDateTimeString(),
        ]);
    }

    public function sitemapListings()
    {
        $listings = \App\Models\Property::where('status', 'active')
            ->orderBy('updated_at', 'desc')
            ->select(['id', 'title', 'district', 'city', 'updated_at'])
            ->get()
            ->map(function ($p) {
                return [
                    'id'         => $p->id,
                    'updated_at' => optional($p->updated_at)->toIso8601String(),
                    'title'      => $p->title ?? '',
                    'district'   => $p->district ?? '',
                    'city'       => $p->city ?? '',
                ];
            });
        return response()->json($listings);
    }

    public function sitemapInventory(\Illuminate\Http\Request $request)
    {
        $minCount = (int) $request->query('min', 3);
        $cities = \App\Models\Property::where('status', 'active')
            ->whereNotNull('city')
            ->selectRaw("LOWER(REPLACE(city, ' ', '-')) as city_slug, COUNT(*) as cnt")
            ->groupBy('city_slug')
            ->having('cnt', '>=', $minCount)
            ->orderByDesc('cnt')
            ->pluck('city_slug')
            ->toArray();
        return response()->json(['property' => $cities]);
    }

    

    public function recent(\Illuminate\Http\Request $request)
    {
        $query = \App\Models\Property::where('status', 'active');
        if ($request->has('property_type')) {
            $query->where('property_type', $request->input('property_type'));
        }
        if ($request->has('listing_type')) {
            $query->where('listing_type', $request->input('listing_type'));
        }
        $properties = $query->orderBy('created_at', 'desc')
            ->limit(12)
            ->get();

        // Bulk-load customer plans to compute real is_pro / is_vip from subscription
        $uids = $properties->pluck('firebase_uid')->filter()->unique()->values()->all();
        $planMap = [];
        if (!empty($uids)) {
            \App\Models\Customer::whereIn('firebase_uid', $uids)
                ->select('firebase_uid', 'bazar_plan', 'plan', 'last_active')
                ->get()
                ->each(function($c) use (&$planMap) {
                    $planMap[$c->firebase_uid] = [
                        'plan' => strtolower($c->bazar_plan ?? $c->plan ?? 'free'),
                        'last_active' => $c->last_active,
                    ];
                });
        }

        // Bulk-load view counts
        $ids = $properties->pluck('id')->all();
        $viewCounts = [];
        if (!empty($ids)) {
            $viewCounts = \Illuminate\Support\Facades\DB::table('property_views')
                ->selectRaw('property_id, COUNT(*) as cnt')
                ->whereIn('property_id', $ids)
                ->groupBy('property_id')
                ->pluck('cnt', 'property_id')
                ->all();
        }

        $result = $properties->map(function($p) use ($planMap, $viewCounts) {
            $images = $p->images;
            if (is_string($images)) {
                try { $images = json_decode($images, true); } catch(\Exception $e) { $images = []; }
            }
            $rawImg = (is_array($images) && count($images) > 0) ? $images[0] : null;
            $imgUrl = $rawImg ? 'https://admin.bazar.uk/storage/' . ltrim($rawImg, '/') : null;

            $sellerInfo = isset($p->firebase_uid) ? ($planMap[$p->firebase_uid] ?? ['plan'=>'free','last_active'=>null]) : ['plan'=>'free','last_active'=>null];
            $sellerPlan = is_array($sellerInfo) ? $sellerInfo['plan'] : $sellerInfo;
            $sellerLastSeen = (is_array($sellerInfo) && $sellerInfo['last_active']) ? $sellerInfo['last_active']->toIso8601String() : null;
            $effectiveIsVip = (bool)$p->is_vip || $sellerPlan === 'vip';
            $effectiveIsPro = (bool)$p->is_pro || in_array($sellerPlan, ['pro', 'vip']);

            return [
                'id'            => $p->id,
                'title'         => $p->title,
                'price'         => $p->price,
                'city'          => $p->city,
                'property_type' => $p->property_type,
                'sub_type'      => $p->sub_type,
                'category'      => $p->category,
                'is_pro'        => $effectiveIsPro,
                'is_vip'        => $effectiveIsVip,
                'photo'         => $imgUrl,
                'bedrooms'      => $p->bedrooms,
                'bathrooms'     => $p->bathrooms,
                'area'          => $p->covered_area,
                'plot'          => $p->plot_area,
                'seller_name'   => $p->seller_name,
                'seller_firebase_uid' => $p->firebase_uid,
                'seller_last_seen' => $sellerLastSeen,
                'views'         => (int)($viewCounts[$p->id] ?? 0),
                'created_at'    => $p->created_at ? $p->created_at->toDateTimeString() : null,
            ];
        });

        return response()->json(['data' => $result]);
    }

    public function byUser($firebaseUid)
    {
        $properties = \App\Models\Property::where('firebase_uid', $firebaseUid)
            ->orderBy('created_at', 'desc')
            ->get();

        // Build a map of view counts from property_views
        $ids = $properties->pluck('id');
        $viewCounts = \Illuminate\Support\Facades\DB::table('property_views')
            ->selectRaw('property_id, COUNT(*) as cnt')
            ->whereIn('property_id', $ids)
            ->groupBy('property_id')
            ->pluck('cnt', 'property_id');

        $typeLabels = [
            'apartment' => 'Apartment', 'studio' => 'Studio', 'house' => 'House',
            'maisonette' => 'Maisonette', 'townhouse' => 'Townhouse', 'penthouse' => 'Penthouse',
            'duplex' => 'Duplex', 'bungalow' => 'Bungalow', 'cottage' => 'Cottage',
            'room' => 'Rooms', 'office' => 'Office', 'shop' => 'Shop',
            'restaurant' => 'Restaurant', 'land' => 'Land', 'building' => 'Building',
            'car' => 'Car', 'motorbike' => 'Motorbike', 'van' => 'Van',
            'mobile_phone' => 'Phone', 'tablet' => 'Tablet', 'other_vehicle' => 'Vehicle',
        ];
        $listingLabels = ['sale' => 'for Sale', 'long_rent' => 'to Rent', 'short_rent' => 'Short Stay', 'rent' => 'to Rent'];

        $result = $properties->map(function($p) use ($viewCounts, $typeLabels, $listingLabels) {
            $images = $p->images;
            if (is_string($images)) {
                try { $images = json_decode($images, true); } catch(\Exception $e) { $images = []; }
            }
            $firstImage = (is_array($images) && count($images) > 0) ? $images[0] : null;

            $typeLabel    = $typeLabels[$p->property_type] ?? ucfirst($p->property_type ?? '');
            $listingLabel = $listingLabels[$p->listing_type] ?? '';
            $category     = trim($typeLabel . ' ' . $listingLabel);

            // Compute expires_at: MAX(created_at, boosted_at) + 30 days
            $baseDate  = $p->boosted_at ?? $p->created_at;
            $expiresAt = $baseDate ? \Carbon\Carbon::parse($baseDate)->addDays(30)->toDateTimeString() : null;

            return [
                'id'            => $p->id,
                'title'         => $p->title,
                'price'         => $p->price,
                'city'          => $p->city,
                'category'      => $category,
                'property_type' => $p->property_type,
                'listing_type'  => $p->listing_type,
                'status'        => $p->status,
                'is_pro'        => (bool)$p->is_pro,
                'is_vip'        => (bool)$p->is_vip,
                'views'         => (int)($viewCounts[$p->id] ?? 0),
                'photo'         => ($firstImage ? 'https://admin.bazar.uk/storage/' . ltrim($firstImage, '/') : null),
                'image'         => ($firstImage ? 'https://admin.bazar.uk/storage/' . ltrim($firstImage, '/') : null),
                'created_at'    => $p->created_at,
                'boosted_at'    => $p->boosted_at,
                'expires_at'    => $expiresAt,
            ];
        });

        return response()->json(['data' => $result]);
    }

    public function setBoost(\Illuminate\Http\Request $request, $id)
    {
        $isInternal = in_array($request->ip(), ['127.0.0.1', '::1', '49.13.231.137']) &&
                      $request->header('X-Bazar-Internal') === 'moderation';

        $firebaseUid = $request->input('firebase_uid');

        if (!$isInternal && !$firebaseUid) {
            return response()->json(['error' => 'Unauthorized'], 403);
        }

        $query = \App\Models\Property::where('id', $id);
        if (!$isInternal && $firebaseUid) {
            $query->where('firebase_uid', $firebaseUid);
        }
        $property = $query->first();

        if (!$property) {
            return response()->json(['error' => 'Property not found'], 404);
        }

        $now = now();
        $property->boosted_at = $now;
        $property->expires_at = $now->copy()->addDays(30);
        $property->is_top     = 1;
        $property->save();

        return response()->json([
            'success'    => true,
            'boosted_at' => $property->boosted_at->toDateTimeString(),
            'expires_at' => $property->expires_at->toDateTimeString(),
        ]);
    }

    public function autoDeleteExpired()
    {
        $isInternal = in_array(request()->ip(), ['127.0.0.1', '::1', '49.13.231.137']) &&
                      request()->header('X-Bazar-Internal') === 'moderation';
        if (!$isInternal) {
            return response()->json(['error' => 'Unauthorized'], 403);
        }

        $cutoff = now()->subDays(30);
        $deleted = \App\Models\Property::where('is_pro', 0)
            ->where('is_vip', 0)
            ->where(function($q) use ($cutoff) {
                $q->where(function($inner) use ($cutoff) {
                    $inner->whereNull('boosted_at')->where('created_at', '<', $cutoff);
                })->orWhere(function($inner) use ($cutoff) {
                    $inner->whereNotNull('boosted_at')->where('boosted_at', '<', $cutoff);
                });
            })
            ->delete();

        return response()->json(['success' => true, 'deleted' => $deleted]);
    }


    public function update(Request $request, $id)
    {
        $firebaseUid = $request->input('firebase_uid');
        if (!$firebaseUid) {
            return response()->json(['error' => 'Authentication required'], 401);
        }

        $property = Property::where('id', $id)->where('firebase_uid', $firebaseUid)->first();
        if (!$property) {
            return response()->json(['error' => 'Property not found or access denied'], 404);
        }

        // Auto old_price: if price is changing, save original as old_price
        if ($request->has('price') && !$request->input('clear_old_price') && !$request->has('old_price')) {
            $newPrice = (float)$request->input('price');
            $oldPrice = (float)$property->price;
            if ($newPrice != $oldPrice && $oldPrice > 0) {
                $property->old_price = $oldPrice;
            }
        }

        // Clear old_price if explicitly requested
        if ($request->input('clear_old_price') == '1') {
            $property->old_price = null;
        }

        $fields = [
            'title','description','listing_type','property_type','sub_type',
            'building_type','parking_type','furnishing_type','ac_type',
            'price','currency','negotiable','country','city','district',
            'region','postal_code','address','latitude','longitude',
            'exact_latitude','exact_longitude','bedrooms','bathrooms',
            'covered_area','plot_area','floor','construction_year',
            'condition','energy_efficiency','online_viewing','registration_block','registration_number','furnished','air_conditioning',
            'parking','pool','garden','veranda','gym','elevator','security',
            'solar_panels','balcony','terrace','central_heating','storage_room',
            'seller_name','seller_phone','seller_email','video_url',
            'car_make','car_model','car_year','mileage','fuel_type',
            'transmission','body_type','colour','doors','seats',
            'drive_type','steering_side','engine_size','previous_owners',
            'service_history','mot_status','phone_brand','phone_model',
            'phone_storage','phone_ram','sim_type','network','battery_health',
            'operating_system','unlock_status','warranty','original_box',
            'charger_included','seller_type', 'old_price',
        ];

        foreach ($fields as $field) {
            if ($request->has($field)) {
                $property->$field = $request->input($field);
            }
        }

        // Boolean fields
        $boolFields = [
            'negotiable','furnished','air_conditioning','parking','pool',
            'garden','veranda','gym','elevator','security','solar_panels',
            'balcony','terrace','central_heating','storage_room',
        ];
        foreach ($boolFields as $field) {
            if ($request->has($field)) {
                $property->$field = filter_var($request->input($field), FILTER_VALIDATE_BOOLEAN);
            }
        }

        // Messenger flags
        if ($request->has('has_whatsapp')) {
            $property->seller_whatsapp = filter_var($request->input('has_whatsapp'), FILTER_VALIDATE_BOOLEAN)
                ? $property->seller_phone : null;
        }
        if ($request->has('has_telegram')) {
            $property->has_telegram = filter_var($request->input('has_telegram'), FILTER_VALIDATE_BOOLEAN);
        }
        if ($request->has('has_viber')) {
            $property->has_viber = filter_var($request->input('has_viber'), FILTER_VALIDATE_BOOLEAN);
        }
        if ($request->has('has_email')) {
            $property->has_email = filter_var($request->input('has_email'), FILTER_VALIDATE_BOOLEAN);
        }

        // Images handling
        $existingImages = is_array($property->images) ? $property->images : (json_decode($property->images ?? '[]', true) ?: []);

        // Plan-based photo limit for update
        $updatePhotoLimit = 10;
        $updateOwner = \App\Models\Customer::where('firebase_uid', $property->firebase_uid)->first();
        if ($updateOwner) {
            $ownerPlan = strtolower($updateOwner->bazar_plan ?? $updateOwner->plan ?? 'free');
            if ($ownerPlan === 'vip') $updatePhotoLimit = 50;
            elseif ($ownerPlan === 'pro') $updatePhotoLimit = 20;
        }

        // Build ordered list of kept existing images (preserving user drag-and-drop order)
        $keepPaths = [];
        if ($request->has('keep_images')) {
            $keepRaw = $request->input('keep_images');
            $keepUrls = is_array($keepRaw) ? $keepRaw : [$keepRaw];
            foreach ($keepUrls as $url) {
                $path = preg_replace('#^https://admin\.bazar\.uk/storage/#', '', $url);
                if (in_array($path, $existingImages)) {
                    $keepPaths[] = $path;
                }
            }
        }

        // Upload new images and collect their paths in order
        $newPaths = [];
        if ($request->hasFile('images')) {
            foreach ($request->file('images') as $image) {
                if (count($keepPaths) + count($newPaths) >= $updatePhotoLimit) break;
                $filename = Str::uuid() . '.' . $image->getClientOriginalExtension();
                $path = $image->storeAs('properties', $filename, 'public');
                $newPaths[] = $path;
            }
        }

        // Use photo_order[] to reconstruct final ordered array respecting drag-and-drop
        if ($request->has('photo_order')) {
            $photoOrder = $request->input('photo_order');
            if (!is_array($photoOrder)) $photoOrder = [$photoOrder];
            $finalImages = [];
            $existIdx = 0;
            $newIdx = 0;
            foreach ($photoOrder as $slot) {
                if (count($finalImages) >= $updatePhotoLimit) break;
                if ($slot === 'exist' && isset($keepPaths[$existIdx])) {
                    $finalImages[] = $keepPaths[$existIdx++];
                } elseif ($slot === 'new' && isset($newPaths[$newIdx])) {
                    $finalImages[] = $newPaths[$newIdx++];
                }
            }
            // Safety net: append any remaining
            while ($existIdx < count($keepPaths) && count($finalImages) < $updatePhotoLimit) {
                $finalImages[] = $keepPaths[$existIdx++];
            }
            while ($newIdx < count($newPaths) && count($finalImages) < $updatePhotoLimit) {
                $finalImages[] = $newPaths[$newIdx++];
            }
            $existingImages = $finalImages;
        } else {
            // Fallback: kept images in user order, then new uploads
            $existingImages = array_slice(array_merge($keepPaths, $newPaths), 0, $updatePhotoLimit);
        }

        // Save (model cast handles json encoding)
        $property->images = $existingImages;

        $property->save();

        return response()->json([
            'success' => true,
            'property_id' => $property->id,
            'message' => 'Ad updated successfully',
        ]);
    }

    public function activatePlan(\Illuminate\Http\Request $request, $id)
    {
        $firebaseUid = $request->input('firebase_uid');
        $plan        = $request->input('plan');

        if (!in_array($plan, ['free', 'pro', 'vip'])) {
            return response()->json(['error' => 'Invalid plan'], 422);
        }

        if ($plan !== 'free' && !$firebaseUid) {
            return response()->json(['error' => 'Authentication required'], 422);
        }

        // For paid plans: verify customer has active subscription
        if ($plan !== 'free') {
            $customer = \App\Models\Customer::where('firebase_uid', $firebaseUid)->first();
            if (!$customer) {
                return response()->json(['error' => 'Customer not found'], 404);
            }
            $customerPlan = $customer->bazar_plan ?? $customer->plan ?? 'free';
            $allowed = ($customerPlan === $plan) || ($customerPlan === 'vip');
            if (!$allowed) {
                return response()->json(['error' => 'No active ' . $plan . ' subscription'], 403);
            }
        }

        $query = \App\Models\Property::where('id', $id);
        if ($firebaseUid) $query->where('firebase_uid', $firebaseUid);
        $property = $query->first();

        if (!$property) {
            return response()->json(['error' => 'Property not found'], 404);
        }

        $property->is_pro = ($plan === 'pro' || $plan === 'vip') ? 1 : 0;
        $property->is_vip = ($plan === 'vip') ? 1 : 0;
        $property->status = 'active';
        $property->save();

        return response()->json(['success' => true, 'id' => $property->id]);
    }


    public function suggest(\Illuminate\Http\Request $request): \Illuminate\Http\JsonResponse
    {
        $q = strtolower(trim($request->get('q', '')));
        if (strlen($q) < 2) {
            return response()->json(['categories' => [], 'listings' => []]);
        }

        $cats = [
            ['label'=>'House for Sale',      'url'=>'/property/house/for-sale',      'keys'=>['house','home','detached','bungalow','cottage']],
            ['label'=>'House to Rent',        'url'=>'/property/house/for-rent',      'keys'=>['house','home','bungalow']],
            ['label'=>'Apartment for Sale',   'url'=>'/property/apartment/for-sale',  'keys'=>['apartment','flat','flats']],
            ['label'=>'Apartment to Rent',    'url'=>'/property/apartment/for-rent',  'keys'=>['apartment','flat','flats']],
            ['label'=>'Studio for Sale',      'url'=>'/property/studio/for-sale',     'keys'=>['studio']],
            ['label'=>'Studio to Rent',       'url'=>'/property/studio/for-rent',     'keys'=>['studio']],
            ['label'=>'Room to Rent',         'url'=>'/property/room/for-rent',       'keys'=>['room','rooms','bedsit']],
            ['label'=>'Maisonette for Sale',  'url'=>'/property/maisonette/for-sale', 'keys'=>['maisonette']],
            ['label'=>'Maisonette to Rent',   'url'=>'/property/maisonette/for-rent', 'keys'=>['maisonette']],
            ['label'=>'Townhouse for Sale',   'url'=>'/property/townhouse/for-sale',  'keys'=>['townhouse','town']],
            ['label'=>'Townhouse to Rent',    'url'=>'/property/townhouse/for-rent',  'keys'=>['townhouse','town']],
            ['label'=>'Penthouse for Sale',   'url'=>'/property/penthouse/for-sale',  'keys'=>['penthouse']],
            ['label'=>'Penthouse to Rent',    'url'=>'/property/penthouse/for-rent',  'keys'=>['penthouse']],
            ['label'=>'Bungalow for Sale',    'url'=>'/property/bungalow/for-sale',   'keys'=>['bungalow']],
            ['label'=>'Cottage for Sale',     'url'=>'/property/cottage/for-sale',    'keys'=>['cottage']],
            ['label'=>'Office for Sale',      'url'=>'/property/office/for-sale',     'keys'=>['office','commercial']],
            ['label'=>'Office to Rent',       'url'=>'/property/office/for-rent',     'keys'=>['office','commercial']],
            ['label'=>'Shop for Sale',        'url'=>'/property/shop/for-sale',       'keys'=>['shop','retail','store']],
            ['label'=>'Shop to Rent',         'url'=>'/property/shop/for-rent',       'keys'=>['shop','retail','store']],
            ['label'=>'Property for Sale',    'url'=>'/property/for-sale',            'keys'=>['property','sale','buy']],
            ['label'=>'Property to Rent',     'url'=>'/property/for-rent',            'keys'=>['property','rent','let']],
        ];

        $matchedCats = [];
        foreach ($cats as $cat) {
            $labelMatch = str_contains(strtolower($cat['label']), $q);
            $keyMatch = false;
            foreach ($cat['keys'] as $kw) {
                if (str_contains($kw, $q) || str_contains($q, $kw)) { $keyMatch = true; break; }
            }
            if ($labelMatch || $keyMatch) {
                $matchedCats[] = ['label' => $cat['label'], 'url' => $cat['url']];
            }
            if (count($matchedCats) >= 5) break;
        }

        $realEstateTypes = ['apartment','house','studio','room','maisonette','townhouse','penthouse','duplex','bungalow','cottage','office','shop','industrial','restaurant','hotel'];
        $listings = \App\Models\Property::where('status', 'active')
            ->whereIn('property_type', $realEstateTypes)
            ->where(function($query) use ($q) {
                $query->where('title', 'like', '%'.$q.'%')
                      ->orWhere('city', 'like', '%'.$q.'%')
                      ->orWhere('district', 'like', '%'.$q.'%')
                      ->orWhere('property_type', 'like', '%'.$q.'%');
            })
            ->select('id','title','city','district','price','listing_type','property_type')
            ->limit(5)
            ->get()
            ->map(function($p) {
                return [
                    'id'    => $p->id,
                    'title' => $p->title,
                    'city'  => $p->city,
                    'price' => $p->price,
                    'url'   => '/'.$p->id,
                ];
            });

        return response()->json(['categories' => $matchedCats, 'listings' => $listings]);
    }


    public function destroy(Request $request, $id)
    {
        $firebaseUid = $request->input('firebase_uid');
        if (!$firebaseUid) {
            return response()->json(['error' => 'Authentication required'], 401);
        }
        $property = Property::where('id', $id)->where('firebase_uid', $firebaseUid)->first();
        if (!$property) {
            return response()->json(['error' => 'Property not found or access denied'], 404);
        }
        $property->delete();
        return response()->json(['success' => true, 'message' => 'Ad deleted']);
    }

    public function setStatus(Request $request, $id)
    {
        $firebaseUid = $request->input('firebase_uid');
        $status = $request->input('status');
        // Internal call from Python moderation server (no user auth required)
        $isInternal = in_array($request->ip(), ['127.0.0.1', '::1', '49.13.231.137']) &&
                      $request->header('X-Bazar-Internal') === 'moderation';
        if (!$isInternal && !$firebaseUid) {
            return response()->json(['error' => 'Authentication required'], 401);
        }
        if (!in_array($status, ['active', 'inactive', 'deleted', 'pending'])) {
            return response()->json(['error' => 'Invalid status'], 422);
        }
        if ($isInternal) {
            $property = Property::where('id', $id)->first();
        } else {
            $property = Property::where('id', $id)->where('firebase_uid', $firebaseUid)->first();
        }
        if (!$property) {
            return response()->json(['error' => 'Property not found or access denied'], 404);
        }
        $property->status = $status;
        $property->save();
        return response()->json(['success' => true, 'status' => $status]);
    }

}