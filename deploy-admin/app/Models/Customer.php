<?php
namespace App\Models;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Facades\Storage;

class Customer extends Model
{
    protected $fillable = [
        'firebase_uid','phone','name','gender','plan',
        'stripe_customer_id','stripe_connect_id','stripe_connect_status',
        'stripe_connected_account_id','stripe_onboarding_completed',
        'stripe_details_submitted','stripe_charges_enabled','stripe_payouts_enabled',
        'bazar_plan','bazar_plan_expires_at','email','address','email','address',
    ];

    protected $casts = [
        'stripe_onboarding_completed' => 'boolean',
        'stripe_details_submitted'    => 'boolean',
        'stripe_charges_enabled'      => 'boolean',
        'stripe_payouts_enabled'      => 'boolean',
        'bazar_plan_expires_at'       => 'datetime',
    ];

    public function subscriptions() { return $this->hasMany(Subscription::class); }
    public function payments()      { return $this->hasMany(Payment::class); }

    protected static function booted(): void
    {
        static::deleting(function (Customer $customer) {
            if (!$customer->firebase_uid) {
                return;
            }

            $properties = \DB::table('properties')
                ->where('firebase_uid', $customer->firebase_uid)
                ->get(['id', 'images']);

            foreach ($properties as $property) {
                $images = json_decode($property->images ?? '[]', true) ?: [];
                foreach ($images as $imagePath) {
                    Storage::disk('public')->delete($imagePath);
                }
            }

            \DB::table('properties')
                ->where('firebase_uid', $customer->firebase_uid)
                ->delete();
        });
    }
}
