# Setting Up Replicate (Flux) for Image Generation

Headless Hero supports two image providers: **Google Gemini** (default) and **Replicate** (running Flux 1.1 Pro). This guide walks through setting up Replicate as your image provider.

---

## 1. Create a Replicate Account

1. Go to [replicate.com](https://replicate.com) and click **Sign up**.
2. You can sign up with your **GitHub** account or an email address.
3. Verify your email if prompted.

## 2. Add Billing

Replicate requires a payment method on file before you can run models.

1. Go to [replicate.com/account/billing](https://replicate.com/account/billing).
2. Click **Add payment method** and enter your card details.
3. Flux 1.1 Pro costs roughly **$0.04 per image** — you only pay for what you use.

## 3. Get Your API Token

1. Go to [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens).
2. Click **Create token**.
3. Give it a name (e.g. "Headless Hero") and copy the token. It starts with `r8_`.
4. Save it somewhere safe — you won't be able to see it again.

## 4. Add the Token in Headless Hero

1. Open Headless Hero.
2. Go to **Settings** (gear icon in the sidebar).
3. Click the **API Keys** tab.
4. Find the **Replicate** field and paste your token.
5. Click **Save**.

## 5. Switch the Image Provider

1. Still in **Settings**, click the **General** tab.
2. Find the **Image Provider** dropdown.
3. Change it from **Google Gemini** to **Replicate (Flux)**.
4. Click **Save**.

That's it — all image generation (scenes and thumbnails) will now use Replicate's Flux 1.1 Pro model.

## Switching Back to Google Gemini

To revert, go to **Settings → General**, change the Image Provider dropdown back to **Google Gemini**, and click **Save**. Your Replicate token stays saved in case you want to switch again later.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "REPLICATE_API_TOKEN is not set" error | Make sure you pasted the token in Settings → API Keys and clicked Save. |
| Images fail to generate | Check that your Replicate account has billing set up and a valid payment method. |
| Want to verify your token works | Go to [replicate.com/account](https://replicate.com/account) and confirm your account is active. |
