-- Demo accounts so the questions section and user details have visible answers.
DELETE FROM users WHERE email IN (
  'demo.anna@guthealth.app',
  'demo.james@guthealth.app',
  'demo.leyla@guthealth.app'
);

INSERT INTO users (
  id, email, full_name, auth_provider, is_active, is_admin,
  onboarding_completed, tracking_started_on
) VALUES
  ('a1111111-1111-4111-8111-111111111201', 'demo.anna@guthealth.app', 'Anna Demo', 'email', true, false, true, DATE '2026-10-10'),
  ('a1111111-1111-4111-8111-111111111202', 'demo.james@guthealth.app', 'James Demo', 'email', true, false, true, DATE '2026-10-11'),
  ('a1111111-1111-4111-8111-111111111203', 'demo.leyla@guthealth.app', 'Leyla Demo', 'email', true, false, true, DATE '2026-10-12');

INSERT INTO onboarding_profiles (
  id, user_id, goals, concerns, interests, target_30_day_goal
) VALUES
  (
    'b1111111-1111-4111-8111-111111111201',
    'a1111111-1111-4111-8111-111111111201',
    '["My bowel regularity"]'::jsonb,
    '["Infrequent bowel movements", "Bloating"]'::jsonb,
    '["Coffee", "Stress", "Sleep"]'::jsonb,
    'Track consistently for 30 days'
  ),
  (
    'b1111111-1111-4111-8111-111111111202',
    'a1111111-1111-4111-8111-111111111202',
    '["How my stool changes"]'::jsonb,
    '["Loose stools", "Pain or discomfort"]'::jsonb,
    '["Dairy", "Spicy food", "Water intake"]'::jsonb,
    'Notice what changes after spicy food'
  ),
  (
    'b1111111-1111-4111-8111-111111111203',
    'a1111111-1111-4111-8111-111111111203',
    '["Patterns between food and digestion"]'::jsonb,
    '["I''m not sure yet"]'::jsonb,
    '["Water intake", "Sleep"]'::jsonb,
    'Keep a simple diary for 30 days'
  );

INSERT INTO survey_answers (
  id, user_id, question_id, option_id, question_title, question_kind, value_text
) VALUES
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111201', '11111111-1111-4111-8111-111111111101', '11111111-1111-4111-8111-111111111101', 'What would you like to understand better?', 'single', 'My bowel regularity'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111201', '11111111-1111-4111-8111-111111111102', '11111111-1111-4111-8111-111111112101', 'Any specific concerns?', 'multi', 'Infrequent bowel movements'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111201', '11111111-1111-4111-8111-111111111102', '11111111-1111-4111-8111-111111112104', 'Any specific concerns?', 'multi', 'Bloating'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111201', '11111111-1111-4111-8111-111111111103', '11111111-1111-4111-8111-111111113101', 'What would you like to track?', 'tiles', 'Coffee'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111201', '11111111-1111-4111-8111-111111111103', '11111111-1111-4111-8111-111111113107', 'What would you like to track?', 'tiles', 'Stress'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111201', '11111111-1111-4111-8111-111111111103', '11111111-1111-4111-8111-111111113108', 'What would you like to track?', 'tiles', 'Sleep'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111201', '11111111-1111-4111-8111-111111111104', NULL, 'Let''s start your 30-day journey', 'text', 'Track consistently for 30 days'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111202', '11111111-1111-4111-8111-111111111101', '11111111-1111-4111-8111-111111111102', 'What would you like to understand better?', 'single', 'How my stool changes'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111202', '11111111-1111-4111-8111-111111111102', '11111111-1111-4111-8111-111111112102', 'Any specific concerns?', 'multi', 'Loose stools'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111202', '11111111-1111-4111-8111-111111111102', '11111111-1111-4111-8111-111111112103', 'Any specific concerns?', 'multi', 'Pain or discomfort'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111202', '11111111-1111-4111-8111-111111111103', '11111111-1111-4111-8111-111111113102', 'What would you like to track?', 'tiles', 'Dairy'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111202', '11111111-1111-4111-8111-111111111103', '11111111-1111-4111-8111-111111113105', 'What would you like to track?', 'tiles', 'Spicy food'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111202', '11111111-1111-4111-8111-111111111103', '11111111-1111-4111-8111-111111113106', 'What would you like to track?', 'tiles', 'Water intake'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111202', '11111111-1111-4111-8111-111111111104', NULL, 'Let''s start your 30-day journey', 'text', 'Notice what changes after spicy food'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111203', '11111111-1111-4111-8111-111111111101', '11111111-1111-4111-8111-111111111103', 'What would you like to understand better?', 'single', 'Patterns between food and digestion'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111203', '11111111-1111-4111-8111-111111111102', '11111111-1111-4111-8111-111111112105', 'Any specific concerns?', 'multi', 'I''m not sure yet'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111203', '11111111-1111-4111-8111-111111111103', '11111111-1111-4111-8111-111111113106', 'What would you like to track?', 'tiles', 'Water intake'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111203', '11111111-1111-4111-8111-111111111103', '11111111-1111-4111-8111-111111113108', 'What would you like to track?', 'tiles', 'Sleep'),
  (gen_random_uuid(), 'a1111111-1111-4111-8111-111111111203', '11111111-1111-4111-8111-111111111104', NULL, 'Let''s start your 30-day journey', 'text', 'Keep a simple diary for 30 days');

INSERT INTO diary_entries (
  id, user_id, date, no_bowel_movement, stress_level, sleep_hours,
  exercise_minutes, water_ml, other_factors, factors
) VALUES
  ('c1111111-1111-4111-8111-111111111201', 'a1111111-1111-4111-8111-111111111201', DATE '2026-10-14', false, 4, 7.5, 20, 1800, 'Busy morning', '["stress","sleep"]'::jsonb),
  ('c1111111-1111-4111-8111-111111111202', 'a1111111-1111-4111-8111-111111111202', DATE '2026-10-14', false, 6, 6.0, 0, 1200, NULL, '["stress"]'::jsonb),
  ('c1111111-1111-4111-8111-111111111203', 'a1111111-1111-4111-8111-111111111203', DATE '2026-10-14', true, 2, 8.0, 30, 2100, NULL, '["sleep","exercise"]'::jsonb);

INSERT INTO bowel_movements (
  id, diary_entry_id, occurred_at, bristol_type, pain_level, blood_present
) VALUES
  (gen_random_uuid(), 'c1111111-1111-4111-8111-111111111201', TIME '08:10', 4, 1, false),
  (gen_random_uuid(), 'c1111111-1111-4111-8111-111111111202', TIME '09:40', 6, 3, false);

INSERT INTO food_drink_logs (
  id, diary_entry_id, kind, name, consumed_at, notes
) VALUES
  (gen_random_uuid(), 'c1111111-1111-4111-8111-111111111201', 'drink', 'Coffee', TIME '07:30', 'One cup'),
  (gen_random_uuid(), 'c1111111-1111-4111-8111-111111111201', 'food', 'Oatmeal', TIME '08:00', NULL),
  (gen_random_uuid(), 'c1111111-1111-4111-8111-111111111202', 'food', 'Spicy noodles', TIME '13:15', 'Lunch'),
  (gen_random_uuid(), 'c1111111-1111-4111-8111-111111111202', 'drink', 'Milk tea', TIME '16:00', NULL),
  (gen_random_uuid(), 'c1111111-1111-4111-8111-111111111203', 'drink', 'Water', TIME '11:00', 'Two glasses'),
  (gen_random_uuid(), 'c1111111-1111-4111-8111-111111111203', 'food', 'Rice and vegetables', TIME '19:30', NULL);
