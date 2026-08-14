-- =================================================================
-- COLLEGE LOST & FOUND MANAGEMENT SYSTEM - DATABASE SCHEMA (11 TABLES)
-- =================================================================

-- 1. ROLES TABLE (Student, Faculty, Admin)
CREATE TABLE IF NOT EXISTS roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) UNIQUE NOT NULL
);

-- 2. USERS TABLE
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    registration_no VARCHAR(30) UNIQUE,
    phone_number VARCHAR(15),
    department VARCHAR(100),
    password_hash VARCHAR(255) NOT NULL,
    role_id INT NOT NULL REFERENCES roles(role_id) ON DELETE NO ACTION,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. CATEGORIES TABLE
CREATE TABLE IF NOT EXISTS categories (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT
);

-- 4. LOCATIONS TABLE
CREATE TABLE IF NOT EXISTS locations (
    location_id SERIAL PRIMARY KEY,
    location_name VARCHAR(150) UNIQUE NOT NULL,
    building VARCHAR(100),
    description TEXT
);

-- 5. ITEMS TABLE
CREATE TABLE IF NOT EXISTS items (
    item_id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    item_type VARCHAR(10) NOT NULL CHECK (item_type IN ('Lost', 'Found')),
    status VARCHAR(20) NOT NULL DEFAULT 'Available' CHECK (status IN ('Available', 'Claimed', 'Returned', 'Archived')),
    category_id INT NOT NULL REFERENCES categories(category_id) ON DELETE NO ACTION,
    location_id INT NOT NULL REFERENCES locations(location_id) ON DELETE NO ACTION,
    reported_by INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    date_reported DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. ITEM IMAGES TABLE
CREATE TABLE IF NOT EXISTS item_images (
    image_id SERIAL PRIMARY KEY,
    item_id INT NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. CLAIMS TABLE
CREATE TABLE IF NOT EXISTS claims (
    claim_id SERIAL PRIMARY KEY,
    item_id INT NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
    claimant_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    proof_description TEXT NOT NULL,
    claim_status VARCHAR(20) NOT NULL DEFAULT 'Pending' CHECK (claim_status IN ('Pending', 'Approved', 'Rejected')),
    reviewed_by INT REFERENCES users(user_id) ON DELETE SET NULL,
    review_remarks TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 8. RETURNED ITEMS TABLE
CREATE TABLE IF NOT EXISTS returned_items (
    return_id SERIAL PRIMARY KEY,
    item_id INT UNIQUE NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
    claim_id INT UNIQUE NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    verified_by_faculty_id INT NOT NULL REFERENCES users(user_id) ON DELETE NO ACTION,
    claimant_registration_no VARCHAR(30) NOT NULL,
    claimant_phone VARCHAR(15) NOT NULL,
    return_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    verification_notes TEXT
);

-- 9. NOTIFICATIONS TABLE
CREATE TABLE IF NOT EXISTS notifications (
    notification_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 10. ANNOUNCEMENTS TABLE
CREATE TABLE IF NOT EXISTS announcements (
    announcement_id SERIAL PRIMARY KEY,
    created_by INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 11. ACTIVITY LOGS TABLE
CREATE TABLE IF NOT EXISTS activity_logs (
    log_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id) ON DELETE SET NULL,
    action_type VARCHAR(100) NOT NULL,
    description TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =================================================================
-- INDEXES FOR PERFORMANCE OPTIMIZATION
-- =================================================================
CREATE INDEX IF NOT EXISTS idx_items_search ON items (status, category_id, location_id);
CREATE INDEX IF NOT EXISTS idx_items_date ON items (date_reported DESC);
CREATE INDEX IF NOT EXISTS idx_claims_status ON claims (claim_status);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications (user_id, is_read);

-- =================================================================
-- INITIAL SEED DATA
-- =================================================================
INSERT INTO roles (role_id, role_name) VALUES 
(1, 'Student'), 
(2, 'Faculty'), 
(3, 'Admin')
ON CONFLICT (role_name) DO NOTHING;

INSERT INTO categories (category_name, description) VALUES 
('Electronics', 'Laptops, phones, chargers, earphones'), 
('ID & Access Cards', 'College IDs, metro cards, keycards'), 
('Wallets & Bags', 'Wallets, purses, backpacks, pouches'), 
('Books & Stationery', 'Textbooks, notebooks, calculators'), 
('Keys', 'Room keys, bike keys'), 
('Clothing & Accessories', 'Jackets, watches, glasses')
ON CONFLICT (category_name) DO NOTHING;

INSERT INTO locations (location_name, building, description) VALUES 
('Central Library', 'Main Block', '1st Floor Reading Hall'), 
('Food Court 1', 'Student Center', 'Ground floor dining area'), 
('Auditorium', 'Academic Block', 'Main entrance lobby')
ON CONFLICT (location_name) DO NOTHING;