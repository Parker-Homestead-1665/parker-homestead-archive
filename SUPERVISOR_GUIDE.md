# Parker Homestead Archive - Supervisor Management Guide

## Overview

The Parker Homestead Virtual Archive is a searchable digital collection of historical books and postcards. This guide will help you add new entries, update existing ones, and maintain the archive after the current curator leaves the organization.

---

## How the Archive Works

### What You're Managing

- **Website**: `index.html` - The interactive archive display that anyone can access
- **Data**: `import_master.csv` - The spreadsheet that powers the entire archive
- **Images**: `images/` folder - Photos of items in the collection
- **Repository**: Stored on GitHub (a free, secure platform)

When you update the CSV file, the website automatically reads the new data and displays it. No coding required!

---

## Step 1: Understanding the CSV File

The `import_master.csv` file is a spreadsheet where each row is one item (book or postcard) in the archive.

### Key Columns You'll Use Most Often:

| Column Name | What It Is | Example |
|---|---|---|
| `id` | Unique ID number | `3437` |
| `Dublin Core:Title` | Item title | `Max Kromer: a story of the seige of Strasburg` |
| `Dublin Core:Creator` | Author/Creator | `Stretton, Hesba` |
| `Dublin Core:Date` | Year/date published | `1871` |
| `Dublin Core:Description` | Notes about condition/notes | `fair\|YA` |
| `Final_Image_Path` | Photo filename | `3437.jpg` |
| `Dublin Core:Publisher` | Publisher name | `Dodd, Mead & Company` |
| `item_type_name` | Is it a Book or Postcard? | `Text` |
| `tags` | Keywords for searching | `History\|Fiction` |

### Other Important Columns:

- `Dublin Core:Identifier` - Call number or shelf location
- `Collection_Name` - Which collection (usually "The Parker Homestead Book Collection")
- `featured` - Set to "TRUE" to highlight an item
- `url` - External link (like to archive.org)
- Item-specific columns for postcards: `Item Type Metadata:Addressee`, `Item Type Metadata:Addressor`, etc.

---

## Step 2: Add a New Item to the Archive

### Option A: Using GitHub Web Interface (Easiest)

1. Go to: https://github.com/emmettromilio/parker-homestead-archive
2. Click the `import_master.csv` file
3. Click the **pencil icon** (Edit) in the top right
4. Scroll to the bottom of the file
5. Add a new line with your item's information

**Example:** Adding a new book
```
"3851","3851.jpg","Smith, John","1920","good condition, inscription on inside cover","85|Shelf","","Publisher Name|City","823.8 SMI","The Complete Works of John Smith","","","","","","","2026-05-18T00:00:00+00:00","1","The Parker Homestead Book Collection","False","0","1","Text","2026-05-18T16:13:11+00:00","65670","True","","https://theparkerhomestead.org"
```

6. Click **Commit changes** at the bottom
7. Add a message like: "Add new book: The Complete Works of John Smith"
8. Click **Commit changes** again

The archive website will update automatically within seconds!

### Option B: For Multiple Items (Recommended)

Use a spreadsheet program like Google Sheets or Excel:

1. Open the `import_master.csv` file locally
2. Add your new rows
3. Save as CSV (not .xlsx)
4. Upload to GitHub:
   - Go to https://github.com/emmettromilio/parker-homestead-archive
   - Click **Add file** → **Upload files**
   - Select your updated `import_master.csv`
   - Click **Commit changes**

---

## Step 3: Add Item Photos

Photos should be **JPG format** and named to match the item ID.

### Example:
- Item ID: `3851`
- Photo filename: `3851.jpg`
- In the CSV column `Final_Image_Path`, put: `3851.jpg`

### To Upload Photos:

1. Go to: https://github.com/emmettromilio/parker-homestead-archive
2. Click the **images** folder
3. Click **Add file** → **Upload files**
4. Select your JPG images
5. Click **Commit changes**

---

## Step 4: Fill in Item Information Correctly

### Title (Required)
- Enter in `Dublin Core:Title`
- Example: `Max Kromer: a story of the siege of Strasburg`

### Author/Creator
- Enter in `Dublin Core:Creator`
- Format: `Last Name, First Name`
- Example: `Stretton, Hesba`

### Date
- Enter in `Dublin Core:Date`
- Can be a year or full date
- Examples: `1871`, `1871-05-15`, `1875?` (for uncertain dates)

### Item Type
- Enter in `item_type_name`
- Should be: `Text` (for books), or other appropriate category
- This is what shows as a badge on cards

### Description/Condition
- Enter in `Dublin Core:Description`
- Include condition and any ownership notes
- Example: `good condition|Gift inscription to Julia Parker`
- Separate multiple notes with the `|` character

### Shelf Location
- Enter in `Dublin Core:Identifier`
- Example: `85|Shelf` or `120|Oversize`

### Publisher
- Enter in `Dublin Core:Publisher`
- Format: `Publisher Name|City`
- Example: `Dodd, Mead & Company|New York`

### Collection
- Enter in `Collection_Name`
- Likely: `The Parker Homestead Book Collection`

### Featured Item (Optional)
- Enter in `featured`
- Put: `TRUE` to highlight, `FALSE` or leave blank for normal items

### External Link (Optional)
- Enter in `Dublin Core:Is Format Of`
- Example: `https://archive.org/details/example123`

---

## Step 5: Update an Existing Item

### Via GitHub Web Interface:

1. Go to: https://github.com/emmettromilio/parker-homestead-archive
2. Click the `import_master.csv` file
3. Click the **pencil icon** to edit
4. Use **Ctrl+F** to find the item ID you want to update
5. Edit the information
6. Click **Commit changes**

### Helpful Tips:
- Don't delete columns or change column names
- Don't delete rows unless absolutely necessary
- Keep the format consistent with other entries

---

## Step 6: Search & Test the Archive

After making changes, test that everything works:

1. Go to: https://emmettromilio.github.io/parker-homestead-archive/
2. Use the search bar to find your new item
3. Click on it to make sure all details display correctly
4. Test the filters (Item Type dropdown)

Changes usually appear within 30 seconds!

---

## Maintaining Permanent Access After Staffing Changes

### The Problem
The archive is currently stored in the personal GitHub account of the current curator (emmettromilio). If they leave the organization, access might be lost.

### The Solution: Transfer to Organization/Team Account

**IMPORTANT:** Do this before anyone leaves!

#### Step 1: Create a Dedicated Organization Account (Free)

1. Go to https://github.com
2. Click your profile → **Settings**
3. Go to **Organizations** → **New Organization**
4. Create a free organization (e.g., "Parker-Homestead" or "Your-Institution-Name")
5. Add team members as needed

#### Step 2: Transfer the Repository

1. Go to: https://github.com/emmettromilio/parker-homestead-archive
2. Click **Settings** (gear icon, top right)
3. Scroll to **Transfer ownership** at the bottom
4. Enter the organization name you created
5. Click **Transfer**

#### Step 3: Grant Access to Team Members

1. Go to the organization's repository
2. Click **Settings** → **Collaborators and teams**
3. Add your supervisors as **Maintainers** (can edit everything)
4. Add other staff as **Collaborators** (can edit but with limitations)

#### Step 4: Update the Website URL

Once transferred, the website will be at:
`https://your-organization-name.github.io/parker-homestead-archive/`

**Update any links** that point to the old URL.

---

## Quick Reference: Most Common Tasks

### Add a Single Book
1. Go to `import_master.csv` on GitHub
2. Click edit (pencil icon)
3. Add a new row at the bottom with:
   - ID number
   - Title
   - Author
   - Year
   - Description/condition
   - Image filename
   - All other required fields (copy from a similar book)
4. Commit changes

### Upload a Photo
1. Go to **images** folder
2. Click **Add file** → **Upload**
3. Select JPG image
4. Commit changes
5. Make sure CSV has matching filename in `Final_Image_Path` column

### Mark Something as Featured
1. Find the item in CSV
2. Change `featured` column to: `TRUE`
3. Commit changes

### Fix a Typo
1. Click pencil icon on CSV
2. Find and fix the error
3. Commit changes

### Delete an Item (if necessary)
1. Edit the CSV file
2. Delete the entire row for that item
3. Commit changes
4. (Optionally delete the photo from images folder)

---

## Troubleshooting

### New items don't appear on the website
- Wait 60 seconds and refresh the page
- Check that you used the correct column headers
- Verify the image filename matches `Final_Image_Path`
- Check for extra spaces or special characters

### Photos won't display
- Make sure filename is JPG (e.g., `3851.jpg`)
- Check that `Final_Image_Path` exactly matches the filename
- File must be in the `images` folder
- Max file size: 25 MB per image

### Item shows but with missing data
- Check that you filled in `Dublin Core:Title` (required)
- Don't leave required columns blank
- Verify you're using the correct column names

### Can't find the file to edit
- Go to: https://github.com/emmettromilio/parker-homestead-archive
- Click the filename you want (e.g., `import_master.csv`)
- Click the pencil icon to edit

---

## Getting Help

### GitHub Support
- If GitHub is confusing, their help docs are at: https://docs.github.com

### CSV Editing Tips
- Keep backup copies of the CSV before making major changes
- Test changes on one item first before updating many items
- Use a text editor (like Notepad++) that preserves the CSV format

### Contact for Archive Questions
- For metadata questions, refer to Dublin Core standards
- For website display questions, check the `index.html` file comments

---

## Important Notes

✅ **DO:**
- Commit changes with descriptive messages
- Test new items appear correctly
- Keep backups of the CSV
- Use the same format for consistent data

❌ **DON'T:**
- Delete column headers
- Change the CSV file structure
- Upload files larger than 25 MB
- Edit the HTML file unless you know what you're doing

---

## Recommended Next Steps

1. **This week**: Have your supervisor create a GitHub organization account
2. **This week**: Transfer the repository to the organization
3. **This week**: Add supervisors as collaborators
4. **Before leaving**: Document any item acquisition procedures
5. **Before leaving**: Create a contact list for any external partners

---

## Questions?

For technical questions about GitHub: https://docs.github.com
For questions about the archive structure, review this guide or the comments in `index.html`.

Good luck maintaining this wonderful historical collection! 📚
