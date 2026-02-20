# LinkedIn API – Initial Setup Guide

This guide walks you through getting **Client ID**, **Client Secret**, and an **Access Token** so this platform can post to LinkedIn on your behalf.

---

## Prerequisites

- A LinkedIn account
- Your app running (e.g. on `http://localhost:8000`) for the OAuth callback

---

## Step 1: Create a LinkedIn App

1. Go to the **LinkedIn Developer Portal**: [https://www.linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)
2. Click **Create app**.
3. Fill in:
   - **App name**: e.g. `My Autopost App`
   - **LinkedIn Page**: create one or pick an existing (required for some products)
   - **Privacy policy URL**: your policy URL (required; can be a placeholder for dev)
   - **App logo**: optional
4. Accept the terms and create the app.

---

## Step 2: Get Client ID and Client Secret

1. In the [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps), open **your app**.
2. Go to the **Auth** tab.
3. Copy:
   - **Client ID** (sometimes labeled “Client ID” or “API Key”)
   - **Client Secret** (click “Show” / “Reveal” to see it)

Add them to your `.env`:

```env
LINKEDIN_CLIENT_ID=your_client_id_here
LINKEDIN_CLIENT_SECRET=your_client_secret_here
```

---

## Step 3: Request “Share on LinkedIn” (Posting Permission)

To post content as a member, you need the **Share on LinkedIn** product and the **w_member_social** scope.

1. In your app, open the **Products** tab.
2. Click **Request access** for **Share on LinkedIn** (or “Marketing Developer Platform” if that’s what your app shows for posting).
3. Complete the form if asked (use case: “Schedule and publish posts to my LinkedIn profile”).
4. Wait for approval if required. Some products are approved quickly; others need review.

Once approved, the **Auth** tab will list **w_member_social** under **OAuth 2.0 scopes**.

---

## Step 4: Add a Redirect URL

1. In your app, go to the **Auth** tab.
2. Under **OAuth 2.0 settings**, find **Redirect URLs**.
3. Click **Add redirect URL** and add one of:
   - Local: `http://localhost:8000/auth/linkedin/callback`
   - Or your public URL, e.g. `https://yourdomain.com/auth/linkedin/callback`
4. Save.

Set the same URL in `.env` (optional; this is the default):

```env
LINKEDIN_REDIRECT_URI=http://localhost:8000/auth/linkedin/callback
```

---

## Step 5: Get an Authorization Code (Browser)

Open this URL in your browser (replace `{client_id}` and `{redirect_uri}`):

```
https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&state=random_state_123&scope=w_member_social
```

Example with a real client ID and local callback:

```
https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fauth%2Flinkedin%2Fcallback&state=random_state_123&scope=w_member_social
```

- **redirect_uri** must be URL-encoded (e.g. `http://localhost:8000/auth/linkedin/callback` → `http%3A%2F%2Flocalhost%3A8000%2Fauth%2Flinkedin%2Fcallback`).
- Log in to LinkedIn if asked and click **Allow**.
- You will be redirected to something like:
  `http://localhost:8000/auth/linkedin/callback?state=random_state_123&code=AQT...long_code...`
- Copy the **code** query parameter (the long string after `code=`). This is your **authorization code** (valid for about 20 minutes).

---

## Step 6: Exchange the Code for an Access Token

Use the authorization code to get an **access_token** (and optionally **refresh_token**).

**Option A – cURL (PowerShell / CMD)**

```bash
curl -X POST "https://www.linkedin.com/oauth/v2/accessToken" ^
  -H "Content-Type: application/x-www-form-urlencoded" ^
  -d "grant_type=authorization_code" ^
  -d "code=PASTE_YOUR_AUTHORIZATION_CODE_HERE" ^
  -d "client_id=YOUR_CLIENT_ID" ^
  -d "client_secret=YOUR_CLIENT_SECRET" ^
  -d "redirect_uri=http://localhost:8000/auth/linkedin/callback"
```

**Option B – Token generator (easiest)**

1. Go to [LinkedIn OAuth Token Generator](https://www.linkedin.com/developers/tools/oauth/token-generator).
2. Select your app.
3. Choose scope **w_member_social**.
4. Click **Generate token** and follow the login/consent flow.
5. Copy the generated **Access token** into your `.env`.

**Option C – Postman**

1. In Postman, add redirect URL `https://oauth.pstmn.io/v1/callback` in the LinkedIn app’s Auth tab.
2. Use Postman’s OAuth 2.0 flow with:
   - Auth URL: `https://www.linkedin.com/oauth/v2/authorization`
   - Access Token URL: `https://www.linkedin.com/oauth/v2/accessToken`
   - Client ID and Client Secret, scope `w_member_social`.
3. After authorizing, copy the **Access token** from the response.

---

## Step 7: Save the Access Token in .env

Add (or update) in your `.env`:

```env
LINKEDIN_ACCESS_TOKEN=your_access_token_here
```

- Access tokens usually last **about 60 days**. When it expires, repeat from **Step 5** (get a new code and exchange it) or use a refresh token if you implemented it.
- Never commit `.env` or share your **Client Secret** or **Access Token**.

---

## Summary Checklist

| Step | Action |
|------|--------|
| 1 | Create app at [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps) |
| 2 | Copy **Client ID** and **Client Secret** from Auth tab → add to `.env` |
| 3 | Request **Share on LinkedIn** (and **w_member_social**) under Products |
| 4 | Add **Redirect URL** (e.g. `http://localhost:8000/auth/linkedin/callback`) in Auth tab |
| 5 | Open authorization URL in browser, approve, copy **code** from callback URL |
| 6 | Exchange **code** for **access_token** (cURL, Token Generator, or Postman) |
| 7 | Put **access_token** in `.env` as `LINKEDIN_ACCESS_TOKEN` |

After this, the platform can use `LINKEDIN_ACCESS_TOKEN` (together with `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET` if needed) for LinkedIn posting. When the token expires, repeat Steps 5–7 to get a new one.
