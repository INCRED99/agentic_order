import { apiFetch } from "./api"; // authenticated fetch helper

// The exact JSON the backend sends for GET /me: snake_case names.
interface ApiMe { // the owner's profile plus the built order address
    login_email: string; // Google login email
    customer_email: string | null; // default sender identity, may be null
    restaurant_name: string | null; // shown name of the restaurant
    restaurant_slug: string; // random 8 character routing label
    order_address: string; // built by the backend, for example mealdesk.orders+abcd1234@gmail.com
}

// The shape the UI uses: camelCase.
export interface Me { // owner profile for the screens
    loginEmail: string; // Google login email
    customerEmail: string | null; // default sender identity
    restaurantName: string | null; // shown name of the restaurant
    restaurantSlug: string; // routing label
    orderAddress: string; // the address customers email their orders to
}

// DECISION PROBLEM: who converts snake_case to camelCase?
// Options: (1) one mapping function per API file, (2) rename the backend fields.
// Chosen: option 1, the same approach as menuApi.ts, ordersApi.ts and approvalsApi.ts.
// Cost: one small mapping function per resource.
export async function getMe(): Promise<Me> { // GET /me
    const row = await apiFetch<ApiMe>("/me"); // profile from the backend
    return { // backend shape -> UI shape
        loginEmail: row.login_email, // renamed field
        customerEmail: row.customer_email, // renamed field
        restaurantName: row.restaurant_name, // renamed field
        restaurantSlug: row.restaurant_slug, // renamed field
        orderAddress: row.order_address, // renamed field
    };
}