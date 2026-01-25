# Provider Directory Structure

This file defines the structure of the **Internal Provider Table** used for geo-based matching.
*Note: The bot does not browse the web for providers. It queries this internal database.*

## Data Columns

| Column Name | Description | Example Data |
| :--- | :--- | :--- |
| **Provider Name** | Name of the individual or clinic | *Sarah Jenkins, LMT* |
| **Credentials** | Professional titles (LMT, PT, CLT, etc.) | *LMT, CLT (Certified Lymphedema Therapist)* |
| **Modalities** | Specific techniques offered | *Vodder MLD, Post-Surgical, Oncology, Deep Tissue* |
| **Address** | Street address | *123 Wellness Blvd, Suite 100* |
| **City** | City name | *Austin* |
| **State** | State abbreviation | *TX* |
| **ZIP** | 5-digit ZIP code | *78701* |
| **Booking URL** | Direct link to booking calendar | *https://#* |
| **Notes** | Special instructions or details | *Specializes in post-lipo fibrosis. Parking in back.* |

## Example CSV Format

```csv
Provider Name,Credentials,Modalities,Address,City,State,ZIP,Booking URL,Notes
"Lymphatic Healing Center","LMT, CLT-LANA","MLD, Compression Fitting, Oncology","4500 Main St","Los Angeles","CA","90048","https://lhc.com/book","Insurance accepted for lymphedema"
"Body Flow Studio","PT, DPT","Orthopedic, Sports Lymphatics","8800 Sunset Blvd","West Hollywood","CA","90069","https://#","Cash based only"
```

## Bot Logic for Matching
1.  **Trigger:** User provides City/State or ZIP AND expresses interest in in-person help.
2.  **Query:** Search the table for matches in the provided City or ZIP.
3.  **Output:**
    *   "I found [Provider Name] in [City]. They specialize in [Modalities]."
    *   "Would you like me to open their booking calendar?"
4.  **Safety:** Always add: *"Please verify their credentials to ensure they fit your specific medical needs."*
