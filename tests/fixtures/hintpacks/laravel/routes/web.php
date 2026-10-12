<?php
use App\Http\Controllers\KycController;
Route::get('/developer/kyc', [KycController::class, 'show'])->name('kyc.show');
