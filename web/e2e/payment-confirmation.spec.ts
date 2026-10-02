import { expect, Page, test } from "@playwright/test";
import { customer, installApiMocks } from "./helpers";

const pendingOrder = {
  id: "order-confirmation",
  order_number: "GO261002CONF01",
  user_id: customer.id,
  store_id: "store-1",
  address_id: "address-1",
  status: "placed",
  payment_method: "upi",
  payment_status: "pending",
  subtotal: "220",
  delivery_fee: "20",
  total: "240",
  created_at: "2026-10-02T00:00:00Z",
  updated_at: "2026-10-02T00:00:00Z",
};
const intent = {
  payment_attempt_id: "attempt-confirmation",
  provider: "razorpay",
  provider_order_id: "provider-order-confirmation",
  amount_subunits: 24000,
  amount: "240",
  currency: "INR",
  key_id: "test-public-key",
};
const cart = {
  id: "cart-confirmation",
  store_id: "store-1",
  subtotal: "220",
  items: [
    {
      id: "cart-item-confirmation",
      store_product_id: "listing-1",
      quantity: 1,
      store_product: {
        id: "listing-1",
        store_id: "store-1",
        product_id: "product-1",
        price: "220",
        stock_quantity: 4,
        is_available: true,
        product: {
          id: "product-1",
          category_id: "category-1",
          name: "Rice",
          unit: "1 kg",
        },
      },
    },
  ],
};
const address = {
  id: "address-1",
  village_id: "village-niphad",
  label: "Home",
  landmark: "Niphad Main Road",
  latitude: 20.0778,
  longitude: 74.1118,
  is_default: true,
};

async function installRazorpaySuccess(page: Page) {
  await page.addInitScript(() => {
    type TestWindow = Window & { __gaononeRazorpayOpens?: number };
    class Razorpay {
      constructor(
        private options: {
          handler: (response: {
            razorpay_payment_id: string;
            razorpay_order_id: string;
            razorpay_signature: string;
          }) => void | Promise<void>;
          modal?: { ondismiss?: () => void };
        },
      ) {}
      open() {
        (window as TestWindow).__gaononeRazorpayOpens =
          ((window as TestWindow).__gaononeRazorpayOpens || 0) + 1;
        void Promise.resolve(
          this.options.handler({
            razorpay_payment_id: "pay-confirmation",
            razorpay_order_id: "provider-order-confirmation",
            razorpay_signature: "signed-confirmation",
          }),
        ).then(() => this.options.modal?.ondismiss?.());
      }
      on() {}
    }
    (window as Window & { Razorpay?: unknown }).Razorpay = Razorpay;
  });
}

test("Orders retries only the existing signed payment confirmation after a transient failure", async ({
  page,
}) => {
  let intentCalls = 0;
  let releaseRetry!: () => void;
  let retryStarted!: () => void;
  const verificationPayloads: unknown[] = [];
  const retryGate = new Promise<void>((resolve) => {
    releaseRetry = resolve;
  });
  const retryRequest = new Promise<void>((resolve) => {
    retryStarted = resolve;
  });
  await installRazorpaySuccess(page);
  await installApiMocks(page, customer);
  await page.route("http://localhost:8000/api/v1/orders/me", (route) =>
    route.fulfill({
      json: [
        {
          ...pendingOrder,
          payment_status: "pending",
        },
      ],
    }),
  );
  await page.route(
    `http://localhost:8000/api/v1/payments/orders/${pendingOrder.id}/intent`,
    (route) => {
      intentCalls += 1;
      return route.fulfill({ json: intent });
    },
  );
  await page.route("http://localhost:8000/api/v1/payments/verify", (route) => {
    verificationPayloads.push(route.request().postDataJSON());
    if (verificationPayloads.length === 1)
      return route.fulfill({
        status: 503,
        json: { detail: "Payment provider is not configured" },
      });
    retryStarted();
    return retryGate.then(() => {
      return route.fulfill({
        json: {
          order_id: pendingOrder.id,
          payment_status: "paid",
          provider_payment_id: "pay-confirmation",
        },
      });
    });
  });

  await page.goto("/orders");
  await page.getByRole("button", { name: "Pay now" }).click();
  await expect(
    page.getByText(
      "Payment confirmation is pending. Retry confirmation instead of paying again.",
    ),
  ).toBeVisible();
  await expect(
    page.getByText("Payment provider is not configured"),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Confirmation pending" }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Confirmation pending" })
    .evaluate((button) => {
      button.removeAttribute("disabled");
      button.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true }),
      );
    });
  expect(intentCalls).toBe(1);
  expect(
    await page.evaluate(
      () =>
        (window as Window & { __gaononeRazorpayOpens?: number })
          .__gaononeRazorpayOpens,
    ),
  ).toBe(1);

  await page.getByRole("button", { name: "Retry confirmation" }).click();
  await retryRequest;
  await expect(
    page.getByRole("button", { name: "Retrying confirmation…" }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Retrying confirmation…" })
    .evaluate((button) => {
      button.removeAttribute("disabled");
      button.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true }),
      );
    });
  expect(verificationPayloads).toHaveLength(2);
  releaseRetry();
  await expect(
    page.getByText(`Payment verified for ${pendingOrder.order_number}.`),
  ).toBeVisible();
  await expect(page.getByText("Payment: Paid")).toBeVisible();
  await expect(page.getByRole("button", { name: "Pay now" })).toHaveCount(0);
  expect(intentCalls).toBe(1);
  expect(verificationPayloads).toEqual([
    {
      payment_attempt_id: intent.payment_attempt_id,
      razorpay_payment_id: "pay-confirmation",
      razorpay_signature: "signed-confirmation",
    },
    {
      payment_attempt_id: intent.payment_attempt_id,
      razorpay_payment_id: "pay-confirmation",
      razorpay_signature: "signed-confirmation",
    },
  ]);
});

test("Orders clears a terminal payment confirmation failure instead of retrying it", async ({
  page,
}) => {
  let intentCalls = 0;
  let paymentStatus = "pending";
  await installRazorpaySuccess(page);
  await installApiMocks(page, customer);
  await page.route("http://localhost:8000/api/v1/orders/me", (route) =>
    route.fulfill({
      json: [{ ...pendingOrder, payment_status: paymentStatus }],
    }),
  );
  await page.route(
    `http://localhost:8000/api/v1/payments/orders/${pendingOrder.id}/intent`,
    (route) => {
      intentCalls += 1;
      return route.fulfill({ json: intent });
    },
  );
  await page.route("http://localhost:8000/api/v1/payments/verify", (route) => {
    paymentStatus = "failed";
    return route.fulfill({
      status: 400,
      json: { detail: "Invalid payment signature" },
    });
  });

  await page.goto("/orders");
  await page.getByRole("button", { name: "Pay now" }).click();
  await expect(
    page.getByText(
      "Payment confirmation could not be completed. The latest order status is shown below.",
    ),
  ).toBeVisible();
  await expect(page.getByText("Invalid payment signature")).toHaveCount(0);
  await expect(page.getByText("Payment: Failed")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Retry confirmation" }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Pay now" })).toHaveCount(0);
  expect(intentCalls).toBe(1);
});

test("checkout retries confirmation without reopening checkout or creating another intent", async ({
  page,
}) => {
  let checkoutCalls = 0;
  let intentCalls = 0;
  let paid = false;
  const verificationPayloads: unknown[] = [];
  await installRazorpaySuccess(page);
  await installApiMocks(page, customer);
  await page.route("http://localhost:8000/api/v1/cart", (route) =>
    route.fulfill({ json: cart }),
  );
  await page.route("http://localhost:8000/api/v1/addresses/me", (route) =>
    route.fulfill({ json: [address] }),
  );
  await page.route("http://localhost:8000/api/v1/payments/config", (route) =>
    route.fulfill({
      json: {
        enabled: true,
        provider: "razorpay",
        key_id: intent.key_id,
        currency: "INR",
      },
    }),
  );
  await page.route("http://localhost:8000/api/v1/cart/quote**", (route) =>
    route.fulfill({
      json: {
        store_id: "store-1",
        address_id: address.id,
        subtotal: "220",
        delivery_fee: "20",
        total: "240",
        serviceable: true,
        inventory_valid: true,
        store_open: true,
        checkout_ready: true,
        blockers: [],
      },
    }),
  );
  await page.route("http://localhost:8000/api/v1/orders/checkout", (route) => {
    checkoutCalls += 1;
    return route.fulfill({ status: 201, json: pendingOrder });
  });
  await page.route(
    `http://localhost:8000/api/v1/payments/orders/${pendingOrder.id}/intent`,
    (route) => {
      intentCalls += 1;
      return route.fulfill({ json: intent });
    },
  );
  await page.route(
    `http://localhost:8000/api/v1/orders/${pendingOrder.id}`,
    (route) =>
      route.fulfill({
        json: {
          ...pendingOrder,
          payment_status: paid ? "paid" : "pending",
          items: [],
        },
      }),
  );
  await page.route("http://localhost:8000/api/v1/orders/me", (route) =>
    route.fulfill({
      json: [
        {
          ...pendingOrder,
          payment_status: paid ? "paid" : "pending",
        },
      ],
    }),
  );
  await page.route("http://localhost:8000/api/v1/payments/verify", (route) => {
    verificationPayloads.push(route.request().postDataJSON());
    if (verificationPayloads.length === 1)
      return route.fulfill({
        status: 503,
        json: { detail: "Payment provider is not configured" },
      });
    paid = true;
    return route.fulfill({
      json: {
        order_id: pendingOrder.id,
        payment_status: "paid",
        provider_payment_id: "pay-confirmation",
      },
    });
  });

  await page.goto("/checkout");
  await page.getByRole("radio", { name: /UPI \/ online payment/ }).check();
  const place = page.getByRole("button", { name: "Place order & pay" });
  await expect(place).toBeEnabled();
  await place.click();
  await expect(
    page.getByText(
      "Payment confirmation is pending. Retry confirmation instead of paying again.",
    ),
  ).toBeVisible();
  await expect(
    page.getByText("Payment provider is not configured"),
  ).toHaveCount(0);
  await expect(place).toBeDisabled();
  await place.evaluate((button) => {
    button.removeAttribute("disabled");
    button.dispatchEvent(
      new MouseEvent("click", { bubbles: true, cancelable: true }),
    );
  });
  expect(checkoutCalls).toBe(1);
  expect(intentCalls).toBe(1);
  expect(
    await page.evaluate(
      () =>
        (window as Window & { __gaononeRazorpayOpens?: number })
          .__gaononeRazorpayOpens,
    ),
  ).toBe(1);

  await page.getByRole("button", { name: "Retry confirmation" }).click();
  await page.waitForURL(
    `/orders?placed=${pendingOrder.order_number}&paid=1`,
  );
  await expect(
    page.getByText(`Order ${pendingOrder.order_number} placed and payment verified.`),
  ).toBeVisible();
  await expect(page.getByText("Payment: Paid")).toBeVisible();
  expect(checkoutCalls).toBe(1);
  expect(intentCalls).toBe(1);
  expect(verificationPayloads).toEqual([
    {
      payment_attempt_id: intent.payment_attempt_id,
      razorpay_payment_id: "pay-confirmation",
      razorpay_signature: "signed-confirmation",
    },
    {
      payment_attempt_id: intent.payment_attempt_id,
      razorpay_payment_id: "pay-confirmation",
      razorpay_signature: "signed-confirmation",
    },
  ]);
});
