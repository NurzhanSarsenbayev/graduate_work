SET search_path TO ugc, public;

INSERT INTO ratings (id, film_id, user_id, rating, created_at)
VALUES
  -- A New Hope
  ('11111111-1111-1111-1111-111111111111', 'aae5751a-865f-4724-9db9-26cafee54e34', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 9, NOW()),
  ('11111111-1111-1111-1111-111111111112', 'aae5751a-865f-4724-9db9-26cafee54e34', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 8, NOW()),

  -- Empire Strikes Back
  ('22222222-2222-2222-2222-222222222221', '0c834d17-f6a4-472b-a5b0-e6e856c96b55', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 10, NOW()),
  ('22222222-2222-2222-2222-222222222222', '0c834d17-f6a4-472b-a5b0-e6e856c96b55', 'cccccccc-cccc-cccc-cccc-cccccccccccc', 9, NOW()),

  -- Return of the Jedi
  ('33333333-3333-3333-3333-333333333331', 'b3bc2fcf-e9dc-4a1b-a32d-98920cb78c75', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 8, NOW()),
  ('33333333-3333-3333-3333-333333333332', 'b3bc2fcf-e9dc-4a1b-a32d-98920cb78c75', 'cccccccc-cccc-cccc-cccc-cccccccccccc', 7, NOW()),

  -- The Force Awakens
  ('44444444-4444-4444-4444-444444444441', '800dba96-d0c7-4a43-8304-d0eebba039cb', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 8, NOW()),
  ('44444444-4444-4444-4444-444444444442', '800dba96-d0c7-4a43-8304-d0eebba039cb', 'dddddddd-dddd-dddd-dddd-dddddddddddd', 7, NOW()),

  -- Rogue One
  ('55555555-5555-5555-5555-555555555551', 'ea7138b8-157f-4e5d-b53d-8b64c63d17cd', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 9, NOW()),
  ('55555555-5555-5555-5555-555555555552', 'ea7138b8-157f-4e5d-b53d-8b64c63d17cd', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 8, NOW());
