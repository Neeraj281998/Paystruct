package com.paystruct.api;

/** The JSON body of every error response. */
public record ApiError(String error, String message) {}
