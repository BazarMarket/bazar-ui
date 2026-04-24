<?php

namespace App\Http\Controllers;

use App\Models\Customer;
use Illuminate\Http\Request;
use Illuminate\Http\JsonResponse;

class CustomerApiController extends Controller
{
    public function store(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'firebase_uid' => 'required|string',
            'phone'        => 'required|string',
            'name'         => 'required|string|max:255',
            'gender'       => 'required|in:male,female',
            'plan'         => 'nullable|string',
        ]);

        $customer = Customer::updateOrCreate(
            ['firebase_uid' => $validated['firebase_uid']],
            [
                'phone'  => $validated['phone'],
                'name'   => $validated['name'],
                'gender' => $validated['gender'],
                'plan'   => $validated['plan'] ?? 'free',
            ]
        );

        return response()->json(['success' => true, 'customer_id' => $customer->id], 201);
    }

    public function show(string $firebaseUid): JsonResponse
    {
        $customer = Customer::where('firebase_uid', $firebaseUid)->first();
        if (!$customer) {
            return response()->json(['exists' => false], 404);
        }
        $expiresAt = $customer->bazar_plan_expires_at;
        $daysLeft   = 0;
        if ($expiresAt) {
            $diff = now()->diffInDays($expiresAt, false);
            $daysLeft = max(0, (int) ceil($diff));
        }
        $adminUids = array_filter(array_map('trim', explode(',', env('ADMIN_FIREBASE_UIDS', ''))));
        $isAdmin = in_array($firebaseUid, $adminUids);
        return response()->json([
            'exists'     => true,
            'name'       => $customer->name,
            'gender'     => $customer->gender,
            'plan'       => $customer->bazar_plan ?? $customer->plan ?? 'free',
            'phone'      => $customer->phone,
            'email'      => $customer->email,
            'address'    => $customer->address,
            'days_left'  => $daysLeft,
            'expires_at'   => $expiresAt,
            'member_since' => $customer->created_at ? $customer->created_at->format('F Y') : null,
            'is_admin'   => $isAdmin,
        ]);
    }

    public function checkPhone(string $phone): JsonResponse
    {
        $exists = Customer::where('phone', $phone)->exists();
        return response()->json(['exists' => $exists]);
    }

    public function update(string $firebaseUid, Request $request): JsonResponse
    {
        $customer = Customer::where('firebase_uid', $firebaseUid)->first();
        if (!$customer) {
            return response()->json(['error' => 'Customer not found'], 404);
        }
        $data = [];
        if ($request->has('email'))   $data['email']   = $request->input('email');
        if ($request->has('address')) $data['address'] = $request->input('address');
        if ($request->has('name'))    $data['name']    = $request->input('name');
        if (!empty($data)) $customer->update($data);
        return response()->json(['success' => true]);
    }

    public function deactivate(string $firebaseUid, \Illuminate\Http\Request $request): JsonResponse
    {
        $customer = Customer::where('firebase_uid', $firebaseUid)->first();
        if (!$customer) {
            return response()->json(['error' => 'Customer not found'], 404);
        }
        $deactivate = (bool) $request->input('deactivate', true);
        $customer->is_deactivated = $deactivate;
        $customer->save();
        return response()->json(['success' => true, 'is_deactivated' => $customer->is_deactivated]);
    }

    public function destroy(string $firebaseUid): JsonResponse
    {
        $customer = Customer::where('firebase_uid', $firebaseUid)->first();
        if (!$customer) {
            return response()->json(['error' => 'Customer not found'], 404);
        }
        // Delete the customer record (removes phone, name, everything)
        $customer->delete();
        return response()->json(['success' => true, 'message' => 'Account deleted']);
    }
}