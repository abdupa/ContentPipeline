<?php
/**
 * Plugin Name:       Product Offers by Content Pipeline
 * Description:       Displays a multi-source price comparison table and history graph for WooCommerce products.
 * Version:           2.2.7 (Stable)
 * Author:            ABDupa
 */

if (!defined('ABSPATH')) { exit; }

// --- Database Table Creation ---
function po_create_price_alerts_table() {
    global $wpdb;
    $table_name = $wpdb->prefix . 'price_alerts';
    $charset_collate = $wpdb->get_charset_collate();

    // V2.3: Added 'last_notified_price' column to track sent alerts
    $sql = "CREATE TABLE $table_name (
        id mediumint(9) NOT NULL AUTO_INCREMENT,
        product_id bigint(20) NOT NULL,
        user_email varchar(100) NOT NULL,
        desired_price decimal(10, 2) NOT NULL,
        last_notified_price decimal(10, 2) DEFAULT NULL,
        status varchar(20) NOT NULL DEFAULT 'active',
        created_at datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
        PRIMARY KEY  (id)
    ) $charset_collate;";

    require_once(ABSPATH . 'wp-admin/includes/upgrade.php');
    dbDelta($sql);
}
register_activation_hook(__FILE__, 'po_create_price_alerts_table');

/**
 * Creates the custom database table for push notification subscriptions upon plugin activation.
 */
function po_create_push_subscriptions_table() {
    global $wpdb;
    $table_name = $wpdb->prefix . 'push_subscriptions';
    $charset_collate = $wpdb->get_charset_collate();

    // V2.3: Added indexes for performance
    $sql = "CREATE TABLE $table_name (
        id mediumint(9) NOT NULL AUTO_INCREMENT,
        product_id bigint(20) NOT NULL,
        onesignal_player_id varchar(36) NOT NULL,
        status varchar(20) NOT NULL DEFAULT 'active',
        created_at datetime DEFAULT '0000-00-00 00:00:00' NOT NULL,
        PRIMARY KEY  (id),
        INDEX product_id_index (product_id)
    ) $charset_collate;";

    require_once(ABSPATH . 'wp-admin/includes/upgrade.php');
    dbDelta($sql);
}

// This tells WordPress to run our new table creation function when the plugin is activated.
register_activation_hook(__FILE__, 'po_create_push_subscriptions_table');

// --- AJAX Handler for Form Submission ---
function po_handle_price_alert_subscription() {
    check_ajax_referer('po_alert_nonce', 'nonce');
    $product_id = isset($_POST['product_id']) ? absint($_POST['product_id']) : 0;
    $email = isset($_POST['email']) ? sanitize_email($_POST['email']) : '';
    $desired_price = isset($_POST['desired_price']) ? round(floatval($_POST['desired_price']), 2) : 0;
    if (empty($product_id) || !is_email($email) || empty($desired_price)) {
        wp_send_json_error(['message' => 'Invalid data provided. Please check your input and try again.']);
    }
    global $wpdb;
    $table_name = $wpdb->prefix . 'price_alerts';
    $existing_alert = $wpdb->get_row($wpdb->prepare("SELECT * FROM $table_name WHERE user_email = %s AND product_id = %d AND status = 'active'", $email, $product_id));
    if ($existing_alert) {
        if ((float)$existing_alert->desired_price === $desired_price) {
            wp_send_json_error(['message' => 'Alert Active: You already have an alert for this product at this price.']);
        } else {
            $wpdb->update($table_name, ['desired_price' => $desired_price, 'created_at' => current_time('mysql')], ['id' => $existing_alert->id], ['%f', '%s'], ['%d']);
            wp_send_json_success(['message' => 'Success! We have updated your alert to the new price.']);
        }
    } else {
        $wpdb->insert($table_name, ['product_id' => $product_id, 'user_email' => $email, 'desired_price' => $desired_price, 'created_at' => current_time('mysql')], ['%d', '%s', '%f', '%s']);
        wp_send_json_success(['message' => 'Success! You will be notified when the price drops.']);
    }
}
add_action('wp_ajax_nopriv_po_subscribe_to_alert', 'po_handle_price_alert_subscription');
add_action('wp_ajax_po_subscribe_to_alert', 'po_handle_price_alert_subscription');


// --- V2.4: NEW AJAX HANDLER FOR PUSH SUBSCRIPTIONS ---
function po_handle_push_alert_subscription() {
    check_ajax_referer('po_push_nonce', 'nonce');

    $product_id = isset($_POST['product_id']) ? absint($_POST['product_id']) : 0;
    $player_id = isset($_POST['player_id']) ? sanitize_text_field($_POST['player_id']) : '';

    if (empty($product_id) || empty($player_id)) {
        wp_send_json_error(['message' => 'Invalid data provided.']);
    }

    global $wpdb;
    $table_name = $wpdb->prefix . 'push_subscriptions';

    // Check for an existing subscription to prevent duplicates
    $existing = $wpdb->get_row($wpdb->prepare("SELECT * FROM $table_name WHERE product_id = %d AND onesignal_player_id = %s", $product_id, $player_id));

    if ($existing) {
        wp_send_json_success(['message' => 'Already Subscribed']);
    } else {
        $wpdb->insert(
            $table_name,
            ['product_id' => $product_id, 'onesignal_player_id' => $player_id, 'created_at' => current_time('mysql')],
            ['%d', '%s', '%s']
        );
        wp_send_json_success(['message' => 'Subscription successful!']);
    }
}
add_action('wp_ajax_nopriv_po_subscribe_to_push_alert', 'po_handle_push_alert_subscription');
add_action('wp_ajax_po_subscribe_to_push_alert', 'po_handle_push_alert_subscription');


// --- Main Shortcode Handler Function (Your Working Code) ---
function product_offers_shortcode_handler($atts) {
    // --- 1. Enqueue All Necessary Assets ---
    $css_version = filemtime(plugin_dir_path(__FILE__) . 'style.css');
    wp_enqueue_style('product-offers-style', plugin_dir_url(__FILE__) . 'style.css', [], $css_version);

    // Chart.js library and our custom chart script
    wp_enqueue_script('chart-js', 'https://cdn.jsdelivr.net/npm/chart.js', [], '4.4.2', true);
    $js_version = filemtime(plugin_dir_path(__FILE__) . 'js/chart-script.js');
    wp_enqueue_script('product-offers-chart-script', plugin_dir_url(__FILE__) . 'js/chart-script.js', ['chart-js'], $js_version, true);

    // Email alert form script
    $alert_js_version = filemtime(plugin_dir_path(__FILE__) . 'js/alert-script.js');
    wp_enqueue_script('product-offers-alert-script', plugin_dir_url(__FILE__) . 'js/alert-script.js', [], $alert_js_version, true);
    
    // NEW: Enqueue the push notification script
    $push_js_version = filemtime(plugin_dir_path(__FILE__) . 'js/push-script.js');
    wp_enqueue_script('product-offers-push-script', plugin_dir_url(__FILE__) . 'js/push-script.js', ['onesignal-sdk'], $push_js_version, true);
    // wp_enqueue_script('product-offers-push-script', plugin_dir_url(__FILE__) . 'js/push-script.js', [], $push_js_version, true);


    // --- 2. Data Fetching & Processing ---
    if (!is_singular('product')) { return ''; }
    $product_id = get_the_ID();
    if (!$product_id) { return ''; }

    $attributes = shortcode_atts(['show' => 'all'], $atts);
    $show_components = array_map('trim', explode(',', $attributes['show']));

    // --- 3. Prepare & Pass Data to JavaScript ---
    
    // Data for Price History Chart
    $winner_history_json = get_post_meta($product_id, '_price_history', true);
    $winner_history_data = !empty($winner_history_json) ? json_decode($winner_history_json, true) : [];
    $chart_data = ['dates' => [], 'prices' => []];
    if(is_array($winner_history_data)){
        foreach ($winner_history_data as $entry) {
            $date = new DateTime($entry['date']);
            $chart_data['dates'][] = $date->format('M j');
            $chart_data['prices'][] = $entry['price'];
        }
    }
    wp_localize_script('product-offers-chart-script', 'poPriceHistoryData', $chart_data);
    
    // Data for Email Alert Form
    $alert_data_for_js = [
        'ajax_url' => admin_url('admin-ajax.php'),
        'nonce'    => wp_create_nonce('po_alert_nonce'),
    ];
    wp_localize_script('product-offers-alert-script', 'poAlertData', $alert_data_for_js);
    
    // NEW: Data for Push Notification Logic
    // Get the OneSignal App ID directly from the settings saved by the OneSignal plugin.
    $onesignal_settings = get_option('OneSignalWP_settings');
    $push_data_for_js = [
        'ajax_url'    => admin_url('admin-ajax.php'),
        'nonce'       => wp_create_nonce('po_push_nonce'),
        'app_id'      => isset($onesignal_settings['app_id']) ? $onesignal_settings['app_id'] : '',
        'product_id'  => $product_id,
    ];
    wp_localize_script('product-offers-push-script', 'poPushData', $push_data_for_js);

    // --- 4. Fetch Data for HTML Rendering ---
    $sources = ['shopee', 'lazada'];
    $offers = [];
    $upload_dir_info = wp_get_upload_dir();
    $logo_base_url = $upload_dir_info['baseurl'] . '/product-offers-logos/';
    foreach ($sources as $source) { 
        $price = get_post_meta($product_id, '_' . $source . '_price', true);
        if (!empty($price) && is_numeric($price)) {
            $offers[] = ['source_name' => ucfirst($source), 'price' => floatval($price), 'url' => get_post_meta($product_id, '_' . $source . '_url', true), 'logo_url' => $logo_base_url . $source . '.png'];
        }
    }
    
    $all_history_entries = [];
    foreach ($sources as $source) { $history_json = get_post_meta($product_id, '_' . $source . '_price_history', true); $history_data = !empty($history_json) ? json_decode($history_json, true) : []; if (is_array($history_data)) { foreach ($history_data as $entry) { $entry['source'] = ucfirst($source); $all_history_entries[] = $entry; } } }
    $highest_price_entry = null; $lowest_price_entry = null; $current_price_entry = null; if (!empty($all_history_entries)) { usort($all_history_entries, function($a, $b) { return strtotime($a['date']) <=> strtotime($b['date']); }); $prices = array_column($all_history_entries, 'price'); $highest_price = max($prices); $lowest_price = min($prices); $highest_price_entry = $all_history_entries[array_search($highest_price, $prices)]; $lowest_price_entry = $all_history_entries[array_search($lowest_price, $prices)]; $current_price_entry = end($all_history_entries); }
    if (empty($offers)) { return ''; }
    usort($offers, function ($a, $b) { return $a['price'] <=> $b['price']; });
    $product_title = get_the_title($product_id);
    
    // --- 5. Start HTML Output ---
    ob_start();
    ?>
    <div class="po-container">
        <?php
        // --- V2.7 FINAL LOGIC: "Button Text Aware" ---
        // This is our single, reliable source of truth for the product's status.
        $product_obj = wc_get_product($product_id);
        $is_phased_out = ($product_obj && strpos($product_obj->get_button_text(), 'Out of Stock') !== false);
        ?>

        <?php // --- MODULE 1: PRICE COMPARISON or PHASED-OUT NOTICE --- ?>
        <?php if (in_array('all', $show_components) || in_array('table', $show_components)) : ?>
            <div class="po-module po-table-module">

                <?php if (!$is_phased_out && !empty($offers)) : ?>
                    <h3 class="po-module-title"><?php echo esc_html($product_title); ?> Price Comparison</h3>
                    <table class="po-table">
                        <tbody>
                            <?php foreach ($offers as $index => $offer) : ?>
                                <tr class="<?php echo ($index === 0) ? 'po-winner' : ''; ?>">
                                    <td class="po-merchant-cell"><a href="<?php echo esc_url($offer['url']); ?>" target="_blank" rel="nofollow noopener"><img src="<?php echo esc_url($offer['logo_url']); ?>" alt="<?php echo esc_attr($offer['source_name']); ?> Logo" class="po-merchant-logo" /><span><?php echo esc_html($offer['source_name']); ?></span></a></td>
                                    <td class="po-price-cell"><a href="<?php echo esc_url($offer['url']); ?>" target="_blank" rel="nofollow noopener"><?php echo '₱' . number_format($offer['price'], 2); ?></a></td>
                                    <td class="po-button-cell"><a href="<?php echo esc_url($offer['url']); ?>" class="po-button" target="_blank" rel="nofollow noopener">BUY NOW</a></td>
                                </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                <?php else: ?>
                    <?php
                    // --- Logic for Phased-Out products with Brand Page Redirect ---
                    $brand = strtolower(explode(' ', $product_title)[0]);

                    // ** THIS IS WHERE YOU WILL ADD YOUR BRAND PAGE MAPPINGS **
                    $brand_price_list_map = [
                        'vivo' => 39938, // vivo -> post id 39938
                        // 'samsung' => 12345, // Example for another brand
                        // 'oppo' => 67890,    // Example for another brand
                    ];

                    $redirect_url = '';
                    if (isset($brand_price_list_map[$brand])) {
                        // If we have a specific price list page for this brand, use it.
                        $redirect_url = get_permalink($brand_price_list_map[$brand]);
                    } else {
                        // Otherwise, fall back to the product's main category page.
                        $category_ids = $product_obj->get_category_ids();
                        if (!empty($category_ids)) {
                            $redirect_url = get_term_link($category_ids[0], 'product_cat');
                        }
                    }
                    ?>
                    <div class="po-phased-out-notice">
                        <p>This product is currently unavailable from our partners. Check out these similar products instead.</p>
                        <a href="<?php echo esc_url($redirect_url); ?>" class="po-button">See Other <?php echo esc_html(ucfirst($brand)); ?> Phones</a>
                    </div>
                <?php endif; ?>
            </div>
        <?php endif; ?>

        <?php // --- MODULE 2: PRICE HISTORY GRAPH (Always shows if data exists) --- ?>
        <?php if ((in_array('all', $show_components) || in_array('history', $show_components)) && !empty($chart_data['dates'])) : ?>
            <div class="po-module po-history-module">
                 <h3 class="po-module-title">Price History</h3>
                 <div class="po-chart-container"><canvas id="po-price-history-chart"></canvas></div>
                 <div class="po-stats-grid"><?php if ($highest_price_entry): ?><div class="po-stat-item"><div class="po-stat-title"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-arrow-up-right-circle" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M1 8a7 7 0 1 0 14 0A7 7 0 0 0 1 8m15 0A8 8 0 1 1 0 8a8 8 0 0 1 16 0M5.854 10.803a.5.5 0 1 1-.708-.707L9.243 6H6.475a.5.5 0 1 1 0-1h3.975a.5.5 0 0 1 .5.5v3.975a.5.5 0 1 1-1 0V6.707z"></path></svg><span>Highest Price</span></div><div class="po-stat-price"><?php echo '₱' . number_format($highest_price_entry['price'], 2); ?> <span class="po-stat-source">on <?php echo esc_html($highest_price_entry['source']); ?></span></div><div class="po-stat-date"><?php echo esc_html((new DateTime($highest_price_entry['date']))->format('M j, Y')); ?></div></div><?php endif; ?><?php if ($lowest_price_entry): ?><div class="po-stat-item"><div class="po-stat-title"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-arrow-down-right-circle" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M1 8a7 7 0 1 0 14 0A7 7 0 0 0 1 8m15 0A8 8 0 1 1 0 8a8 8 0 0 1 16 0M5.854 5.146a.5.5 0 1 0-.708-.708L9.243 9.95H6.475a.5.5 0 1 0 0 1h3.975a.5.5 0 0 0 .5-.5V6.475a.5.5 0 1 0-1 0v2.768z"></path></svg><span>Lowest Price</span></div><div class="po-stat-price"><?php echo '₱' . number_format($lowest_price_entry['price'], 2); ?> <span class="po-stat-source">on <?php echo esc_html($lowest_price_entry['source']); ?></span></div><div class="po-stat-date"><?php echo esc_html((new DateTime($lowest_price_entry['date']))->format('M j, Y')); ?></div></div><?php endif; ?><?php if ($current_price_entry): ?><div class="po-stat-item"><div class="po-stat-title"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-check-circle" viewBox="0 0 16 16"><path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14m0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16"></path><path d="m10.97 4.97-.02.022-3.473 4.425-2.093-2.094a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-1.071-1.05"></path></svg><span>Current Price</span></div><div class="po-stat-price po-stat-price-current"><?php echo '₱' . number_format($current_price_entry['price'], 2); ?> <span class="po-stat-source">on <?php echo esc_html($current_price_entry['source']); ?></span></div><div class="po-stat-date"><?php echo esc_html((new DateTime($current_price_entry['date']))->format('M j, Y')); ?></div></div><?php endif; ?></div>
            </div>
        <?php endif; ?>

        <?php // --- MODULE 3: PRICE ALERT FORM (Only shows if the product is IN STOCK) --- ?>
        <?php if (!$is_phased_out && (in_array('all', $show_components) || in_array('alert', $show_components))) : ?>
             <div class="po-module po-alert-module">
                <h3 class="po-module-title">Create Price Drop Alert</h3>
                <div class="po-alert-body">
                    <p class="po-alert-subtitle">Get notified when the price for <strong><?php echo esc_html($product_title); ?></strong> drops.</p>
                    <button id="po-push-alert-button" class="po-button po-push-button"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-bell-fill" viewBox="0 0 16 16"><path d="M8 16a2 2 0 0 0 2-2H6a2 2 0 0 0 2 2m.995-14.901a1 1 0 1 0-1.99 0A5 5 0 0 0 3 6c0 1.098-.5 6-2 7h14c-1.5-1-2-5.902-2-7 0-2.42-1.72-4.44-4.005-4.901z"/></svg><span>Notify me via Push Alert</span></button>
                    <div class="po-alert-separator"><span>OR</span></div>
                    <form id="po-alert-form"><input type="hidden" name="product_id" value="<?php echo esc_attr($product_id); ?>"><div class="po-alert-inputs"><input type="email" name="email" placeholder="Your Email Address" required class="po-alert-input"><div class="po-alert-price-group"><span>₱</span><input type="number" name="desired_price" placeholder="Desired Price" required class="po-alert-input po-alert-price-input" step="0.01"></div><button type="submit" class="po-button po-alert-button">Set Email Alert</button></div><div class="po-alert-messages"><div class="po-alert-loading" style="display: none;">Setting alert...</div><div class="po-alert-success" style="display: none;"></div><div class="po-alert-error" style="display: none;"></div></div></form>
                </div>
             </div>
        <?php endif; ?>

    </div>
    <?php
    return ob_get_clean();
}
add_shortcode('product_offers', 'product_offers_shortcode_handler');


// --- Cloudflare Rocket Loader Compatibility ---
function po_add_rocket_loader_ignore_attribute($tag, $handle) {
    if ('product-offers-chart-script' === $handle || 'product-offers-alert-script' === $handle) {
        return str_replace(' src', ' data-cfasync="false" src', $tag);
    }
    return $tag;
}
add_filter('script_loader_tag', 'po_add_rocket_loader_ignore_attribute', 10, 2);


// ===================================================================
// --- V2.2 FINAL: WP-Cron Scheduled Task & Manual Trigger ---
// ===================================================================

// The main logic function that runs on the schedule.
function po_check_for_price_drops() {
    global $wpdb;
    $alerts_table = $wpdb->prefix . 'price_alerts';
    $active_alerts = $wpdb->get_results("SELECT * FROM $alerts_table WHERE status = 'active'");

    if (empty($active_alerts)) { return; }

    foreach ($active_alerts as $alert) {
        $product = wc_get_product($alert->product_id);
        if (!$product) { continue; }

        $current_price = (float) $product->get_price();
        $desired_price = (float) $alert->desired_price;
        // Get the price of the last notification we sent. Will be NULL for new alerts.
        $last_notified_price = $alert->last_notified_price !== null ? (float) $alert->last_notified_price : null;

        // --- NEW V2.3 LOGIC ---
        // The condition to send an alert is now threefold:
        // 1. The current price must be below the user's desired price.
        // 2. AND the current price must be lower than the last price we notified them about.
        //    (This stops us from sending an email every day if the price doesn't change).
        // 3. OR this is the very first time we're notifying them (last_notified_price is NULL).
        if ($current_price > 0 && $current_price <= $desired_price && ($last_notified_price === null || $current_price < $last_notified_price)) {
            
            $product_name = $product->get_name();
            $product_url = $product->get_permalink();
            $to = $alert->user_email;
            $subject = 'Price Drop Alert for ' . $product_name;
            $body = "Hi there,<br><br>Good news! The price for <strong>" . esc_html($product_name) . "</strong> has dropped to a new low of <strong>₱" . number_format($current_price, 2) . "</strong>.<br><br>";
            $body .= "You can view the product here: <a href='" . esc_url($product_url) . "'>" . esc_url($product_url) . "</a><br><br>";
            $body .= "Thank you,<br>The GadgetPH Team";
            $headers = ['Content-Type: text/html; charset=UTF-8'];

            $is_sent = wp_mail($to, $subject, $body, $headers);

            if ($is_sent) {
                // Instead of deactivating the alert, we now UPDATE it with the new price.
                // The status remains 'active' for future checks.
                $wpdb->update(
                    $alerts_table,
                    ['last_notified_price' => $current_price],
                    ['id' => $alert->id],
                    ['%f'],
                    ['%d']
                );
            }
        }
    }
}
add_action('po_daily_price_check_event', 'po_check_for_price_drops');


// Schedules the event upon plugin activation to run daily at 1:00 AM.
function po_schedule_price_check_event() {
    if (!wp_next_scheduled('po_daily_price_check_event')) {
        $timezone_string = get_option('timezone_string') ?: 'UTC';
        $timezone = new DateTimeZone($timezone_string);
        $next_run = new DateTime('tomorrow 1:00 AM', $timezone);
        wp_schedule_event($next_run->getTimestamp(), 'daily', 'po_daily_price_check_event');
    }
}
register_activation_hook(__FILE__, 'po_schedule_price_check_event');


// Clean up the schedule upon plugin deactivation.
function po_clear_scheduled_event() {
    wp_clear_scheduled_hook('po_daily_price_check_event');
}
register_deactivation_hook(__FILE__, 'po_clear_scheduled_event');


// Manual Cron Trigger for Testing.
function po_manual_cron_trigger() {
    if (isset($_GET['po_run_price_check']) && $_GET['po_run_price_check'] === 'true') {
        if (!current_user_can('manage_options')) {
            wp_die('You do not have permission to perform this action.');
        }
        echo "Manually triggering the price check task...";
        po_check_for_price_drops();
        echo "<br>Task execution finished.";
        exit;
    }
}
add_action('init', 'po_manual_cron_trigger');


// --- Custom Sender Email and Name ---
function po_custom_mail_from_name($original_email_from) { return 'GadgetPH Alerts'; }
function po_custom_mail_from($original_email_address) { return 'admin@gadgetph.com'; }
add_filter('wp_mail_from_name', 'po_custom_mail_from_name');
add_filter('wp_mail_from', 'po_custom_mail_from');

// --- FINAL FIX: Tell Cloudflare Rocket Loader & Other Optimizers to ignore our scripts ---
// --- V2.5 FINAL FIX: Tell Cloudflare & Other Optimizers to ignore our scripts ---
function po_add_ignore_attribute_to_scripts($tag, $handle) {
    if ('product-offers-chart-script' === $handle || 'product-offers-alert-script' === $handle || 'product-offers-push-script' === $handle) {
        return str_replace(' src', ' data-cfasync="false" data-no-minify="1" src', $tag);
    }
    return $tag;
}
add_filter('script_loader_tag', 'po_add_ignore_attribute_to_scripts', 10, 2);