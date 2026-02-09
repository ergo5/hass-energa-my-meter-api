# Energa "Mój Licznik" API Reference

Unofficial documentation of the Energa Mój Licznik REST API, based on reverse-engineering of the official iOS app.

---

## Base URL

```
https://api-mojlicznik.energa-operator.pl/dp
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/apihelper/SessionStatus` | GET | Initialize session (required before login) |
| `/apihelper/UserLogin` | GET | User authentication |
| `/resources/user/data` | GET | User data, meters, and latest measurements |
| `/resources/mchart` | GET | Hourly chart data (energy history) |

---

## Authentication

### Login Flow

1. **Initialize session** — call `/apihelper/SessionStatus` to obtain session cookies
2. **Login** — call `/apihelper/UserLogin` with the parameters below

### Login Parameters

```
clientOS=ios
notifyService=APNs
username=<email>
password=<password>
token=<device_token>    // 64-char hex, unique per installation
```

### Device Token

- Must be unique per integration installation
- Generated with: `secrets.token_hex(32)`
- Stored persistently in the HA config entry
- **Critical**: without a persistent `device_token`, re-login may fail

### Session Management

- Session is cookie-based (`JSESSIONID`, `TS015b8f91`)
- The server-returned `token` may be empty in newer API versions — cookies are sufficient
- Sessions expire after a few hours — the integration re-authenticates automatically on `401`/`403`

---

## User Data (`/resources/user/data`)

### Response Structure: `response.meterPoints[]`

Primary array containing all registered meters.

```json
{
  "id": "339038",
  "name": "Warszawska 1/1",
  "dev": "35166491",
  "tariff": "G11",
  "agreementPoints": [{
    "code": "590243xxx..."
  }],
  "lastMeasurements": [{
    "zone": "A+ strefa 1",
    "value": 51.989,
    "date": "1766530800000"
  }, {
    "zone": "A- strefa 1",
    "value": 26627.646
  }],
  "meterObjects": [{
    "obis": "1-0:1.8.0*255",
    "label": "DATA.PANEL.ENERGY.A.PLUS"
  }, {
    "obis": "1-0:2.8.0*255",
    "label": "Energia wyprodukowana"
  }]
}
```

**Key fields extracted by the integration:**

| Field | Source | Description |
|-------|--------|-------------|
| `meter_point_id` | `meterPoints[].id` | Meter identifier (used for chart queries) |
| `meter_serial` | `meterPoints[].dev` | Physical meter serial number |
| `tariff` | `meterPoints[].tariff` | Tariff type (e.g. G11) |
| `ppe` | `agreementPoints[].code` | PPE identification number |
| `total_plus` | `lastMeasurements[].value` where zone contains `A+` | Total import reading (kWh) |
| `total_minus` | `lastMeasurements[].value` where zone contains `A-` | Total export reading (kWh) — prosumers only |
| `obis_plus` | `meterObjects[].obis` starting with `1-0:1.8.0` | OBIS code for import |
| `obis_minus` | `meterObjects[].obis` starting with `1-0:2.8.0` | OBIS code for export |
| `address` | `agreementPoints[].address` or `meterPoints[].name` | Installation address (fallback to meter name) |
| `contract_date` | `agreementPoints[].dealer.start` | Contract activation date (timestamp in ms) |

### Legacy vs New API

The PPE number (`code`) and address may appear in different locations:

| Version | PPE Location | Address |
|---------|-------------|---------|
| **New API** | Nested in `meterPoints[].agreementPoints[]` | May be absent (uses `name` as fallback) |
| **Legacy API** | Top-level `response.agreementPoints[]` | Available in `agreementPoints[].address` |

The integration handles both versions with automatic fallback.

---

## Consumer vs Prosumer

| Property | Consumer | Prosumer |
|----------|----------|----------|
| `total_minus` (export reading) | Not available | Float value |
| `A- strefa 1` measurement | Absent | Present |
| OBIS `1-0:2.8.0*255` | Present but no data | Present with data |

---

## Chart API (`/resources/mchart`)

Used to retrieve hourly energy data for a specific day.

### Parameters

```
meterPoint=339038
type=DAY
meterObject=1-0:1.8.0*255
mainChartDate=1766530800000    // day midnight timestamp (ms)
token=<optional>
```

### Response

```json
{
  "response": {
    "mainChart": [
      { "zones": [0.11] },
      { "zones": [0.101] },
      ...
    ]
  }
}
```

### Notes

- **24 data points** = complete day (one per hour, 00:00–23:00)
- **22–23 data points** = current day (still incomplete)
- **Empty response** = no data available or inactive meter
- Export data (`A-` / `1-0:2.8.0`) returns empty for consumer accounts

---

## Required Headers

```
User-Agent: Energa/3.1.2 (pl.energa-operator.mojlicznik; build:1; iOS 16.6.1) Alamofire/5.6.4
Accept: application/json
Accept-Language: pl-PL;q=1.0, en-PL;q=0.9
Content-Type: application/json
```

> **Note:** The API may reject requests with a different `User-Agent`.

---

## Error Handling

| HTTP Status | Meaning | Integration Behavior |
|-------------|---------|---------------------|
| `200` | Success | Parse JSON response |
| `401` / `403` | Session expired or invalid token | Automatic re-login with device token |
| `429` | Rate limited | Retry with backoff |
| `500` | Server error (sporadic) | Retry with exponential backoff |

---

## Rate Limits

- No exact limits documented by Energa
- Observed: `429` responses during intensive querying
- Recommendation: max 1 request/second

---

*Last updated: 2026-02-09*
