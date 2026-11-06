<?php
/**
 * Plugin Name: Media sizes off (wp-essentials)
 * Description: Stops the image copies WordPress core makes regardless of Settings > Media
 *              (1536x1536, 2048x2048 and the "-scaled" original). Delete this file to restore defaults.
 *
 * Install only after the site owner agrees: copy to wp-content/mu-plugins/. Sizes registered by the
 * theme or plugins (e.g. WooCommerce) are kept unless WP_ESSENTIALS_ALL_SIZES_OFF is true in wp-config.php.
 */
defined( 'ABSPATH' ) || exit;

add_filter( 'big_image_size_threshold', '__return_false' );

add_filter(
	'intermediate_image_sizes_advanced',
	static function ( $sizes ) {
		if ( defined( 'WP_ESSENTIALS_ALL_SIZES_OFF' ) && WP_ESSENTIALS_ALL_SIZES_OFF ) {
			return array();
		}
		unset( $sizes['1536x1536'], $sizes['2048x2048'] );
		return $sizes;
	}
);
