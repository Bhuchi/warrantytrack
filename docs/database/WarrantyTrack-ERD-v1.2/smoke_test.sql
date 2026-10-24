-- WarrantyTrack v1.2 schema smoke test. Run AFTER schema.sql on a TEST DB.
-- Success should show NOTICE lines and the final ROLLBACK; no rows persist.
-- Launch: psql -v ON_ERROR_STOP=1 -f smoke_test.sql
BEGIN;
DO $$
DECLARE
  uid uuid := gen_random_uuid();
  cid uuid := gen_random_uuid();
  vid uuid := gen_random_uuid();
  aid uuid := gen_random_uuid();
  wid uuid := gen_random_uuid();
  bad_aid uuid;
  missing_warranty uuid;
  seen integer;
BEGIN
  INSERT INTO users(id,cognito_sub,email,display_name)
    VALUES(uid,'smoke-'||uid::text,('smoke-'||uid::text||'@example.invalid')::citext,'Schema Test User');
  INSERT INTO categories(id,name) VALUES(cid,'smoke-category-'||cid::text);
  INSERT INTO vendors(id,name) VALUES(vid,'smoke-vendor-'||vid::text);

  -- Happy path: serial, vendor, category, invoice, and warranty all present.
  INSERT INTO assets(id,personal_owner_user_id,created_by,product_name,
      serial_number,category_id,vendor_id,purchase_date,invoice_number,
      purchase_price,primary_warranty_id)
    VALUES(aid,uid,uid,'Smoke Test Laptop','SERIAL123',cid,vid,current_date,
      'INV-123',25000.00,wid);
  INSERT INTO warranties(id,asset_id,warranty_type,provider_name,starts_on,
      expires_on,duration_months)
    VALUES(wid,aid,'standard','Smoke Warranty Provider',current_date,
      current_date + 365,12);

  SELECT count(*) INTO seen FROM asset_warranty_status
    WHERE asset_id=aid AND warranty_status='active';
  IF seen != 1 THEN RAISE EXCEPTION 'Expected active warranty status for happy path'; END IF;
  RAISE NOTICE 'PASS: asset + warranty transaction works';

  -- Empty serial must be rejected by CHECK.
  BEGIN
    INSERT INTO assets(id,personal_owner_user_id,created_by,product_name,
        serial_number,category_id,vendor_id,purchase_date,invoice_number,
        purchase_price,primary_warranty_id)
      VALUES(gen_random_uuid(),uid,uid,'Bad Serial',' ',cid,vid,current_date,
        'INV-BAD',100.00,gen_random_uuid());
    RAISE EXCEPTION 'FAIL: blank serial number was accepted';
  EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'PASS: blank serial number rejected';
  END;

  -- Empty invoice must be rejected by CHECK.
  BEGIN
    INSERT INTO assets(id,personal_owner_user_id,created_by,product_name,
        serial_number,category_id,vendor_id,purchase_date,invoice_number,
        purchase_price,primary_warranty_id)
      VALUES(gen_random_uuid(),uid,uid,'Bad Invoice','SERIAL456',cid,vid,current_date,
        ' ',100.00,gen_random_uuid());
    RAISE EXCEPTION 'FAIL: blank invoice was accepted';
  EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'PASS: blank invoice number rejected';
  END;

  -- Required catalog foreign keys cannot be NULL.
  BEGIN
    INSERT INTO assets(id,personal_owner_user_id,created_by,product_name,
        serial_number,category_id,vendor_id,purchase_date,invoice_number,
        purchase_price,primary_warranty_id)
      VALUES(gen_random_uuid(),uid,uid,'No Vendor','SERIAL789',cid,NULL,current_date,
        'INV-NOVENDOR',100.00,gen_random_uuid());
    RAISE EXCEPTION 'FAIL: asset without vendor was accepted';
  EXCEPTION WHEN not_null_violation THEN
    RAISE NOTICE 'PASS: vendor is required';
  END;

  BEGIN
    INSERT INTO assets(id,personal_owner_user_id,created_by,product_name,
        serial_number,category_id,vendor_id,purchase_date,invoice_number,
        purchase_price,primary_warranty_id)
      VALUES(gen_random_uuid(),uid,uid,'No Category','SERIAL999',NULL,vid,current_date,
        'INV-NOCAT',100.00,gen_random_uuid());
    RAISE EXCEPTION 'FAIL: asset without category was accepted';
  EXCEPTION WHEN not_null_violation THEN
    RAISE NOTICE 'PASS: category is required';
  END;

  -- A primary warranty must actually be created for the asset.
  BEGIN
    bad_aid := gen_random_uuid();
    missing_warranty := gen_random_uuid();
    INSERT INTO assets(id,personal_owner_user_id,created_by,product_name,
        serial_number,category_id,vendor_id,purchase_date,invoice_number,
        purchase_price,primary_warranty_id)
      VALUES(bad_aid,uid,uid,'No Warranty','SERIAL000',cid,vid,current_date,
        'INV-NOWAR',100.00,missing_warranty);
    SET CONSTRAINTS assets_primary_warranty_same_asset IMMEDIATE;
    RAISE EXCEPTION 'FAIL: asset without warranty was accepted';
  EXCEPTION WHEN foreign_key_violation THEN
    RAISE NOTICE 'PASS: required primary warranty FK rejects missing warranty';
  END;

  -- Make sure there is no physical_condition column in v1.2.
  SELECT count(*) INTO seen FROM information_schema.columns
    WHERE table_schema=current_schema() AND table_name='assets'
      AND column_name='physical_condition';
  IF seen != 0 THEN RAISE EXCEPTION 'FAIL: physical_condition should be postponed'; END IF;
  RAISE NOTICE 'PASS: physical condition is not part of current asset schema';
END $$;
SET CONSTRAINTS ALL IMMEDIATE;
ROLLBACK;
