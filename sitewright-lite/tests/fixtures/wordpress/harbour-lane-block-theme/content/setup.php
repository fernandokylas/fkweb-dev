<?php
/**
 * Loads the Harbour Lane fixture pages into a disposable WordPress (Playground) instance.
 * Run only after wp-load.php. Never point this at a live site: it creates pages and changes the front page.
 *
 * @package harbour-lane
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit( "Load WordPress first.\n" );
}

// Page content includes a Custom HTML form; save it as an administrator would so kses keeps it.
wp_set_current_user( 1 );

$sitewright_dir      = __DIR__;
$sitewright_manifest = json_decode( file_get_contents( $sitewright_dir . '/pages.json' ), true );
if ( ! is_array( $sitewright_manifest ) || empty( $sitewright_manifest['pages'] ) ) {
	exit( "pages.json is missing or invalid.\n" );
}

$sitewright_ids = array();
foreach ( $sitewright_manifest['pages'] as $sitewright_page ) {
	$sitewright_existing = get_page_by_path( $sitewright_page['slug'], OBJECT, 'page' );
	$sitewright_postarr  = array(
		'post_type'    => 'page',
		'post_status'  => 'publish',
		'post_name'    => $sitewright_page['slug'],
		'post_title'   => $sitewright_page['title'],
		'post_excerpt' => $sitewright_page['excerpt'],
		'menu_order'   => (int) $sitewright_page['menu_order'],
		'post_content' => file_get_contents( $sitewright_dir . '/' . basename( $sitewright_page['file'] ) ),
	);
	if ( $sitewright_existing ) {
		$sitewright_postarr['ID'] = $sitewright_existing->ID;
	}
	$sitewright_id = wp_insert_post( wp_slash( $sitewright_postarr ), true );
	if ( is_wp_error( $sitewright_id ) ) {
		exit( 'Could not save ' . $sitewright_page['slug'] . ': ' . $sitewright_id->get_error_message() . "\n" );
	}
	if ( '' !== $sitewright_page['template'] ) {
		update_post_meta( $sitewright_id, '_wp_page_template', $sitewright_page['template'] );
	} else {
		delete_post_meta( $sitewright_id, '_wp_page_template' );
	}
	$sitewright_ids[ $sitewright_page['slug'] ] = $sitewright_id;
}

// Remove the default sample page so the page list shows only the planned site map.
$sitewright_sample = get_page_by_path( 'sample-page', OBJECT, 'page' );
if ( $sitewright_sample ) {
	wp_delete_post( $sitewright_sample->ID, true );
}

update_option( 'blogname', 'Harbour Lane Bakery' );
update_option( 'blogdescription', 'Bread and celebration cakes on Harbour Lane' );
update_option( 'show_on_front', 'page' );
update_option( 'page_on_front', $sitewright_ids[ $sitewright_manifest['front_page'] ] );
update_option( 'permalink_structure', '/%postname%/' );
flush_rewrite_rules();

echo 'Loaded pages: ' . implode( ', ', array_keys( $sitewright_ids ) ) . "\n";
