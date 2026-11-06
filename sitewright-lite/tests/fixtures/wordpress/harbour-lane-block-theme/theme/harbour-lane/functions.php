<?php
/**
 * Harbour Lane fixture theme: scoped assets only. Presets and styles live in theme.json.
 *
 * @package harbour-lane
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

add_action(
	'after_setup_theme',
	function () {
		add_editor_style( 'assets/theme.css' );
	}
);

add_action(
	'init',
	function () {
		$version = wp_get_theme()->get( 'Version' );
		wp_register_script(
			'harbour-lane-order',
			get_theme_file_uri( 'assets/order.js' ),
			array(),
			$version,
			array( 'in_footer' => true )
		);
	}
);

add_action(
	'wp_enqueue_scripts',
	function () {
		wp_enqueue_style( 'harbour-lane', get_theme_file_uri( 'assets/theme.css' ), array(), wp_get_theme()->get( 'Version' ) );
	}
);

/*
 * The order form is a Custom HTML block (no form plugin is chosen yet: OPEN-2), so its simulated
 * handler loads only on pages that render that form. Block templates render before wp_head, so the
 * script is registered on init and enqueued here.
 */
add_filter(
	'render_block_core/html',
	function ( $content ) {
		if ( false !== strpos( $content, 'id="order-form"' ) ) {
			wp_enqueue_script( 'harbour-lane-order' );
		}
		return $content;
	}
);

/*
 * Meta description from the page excerpt (page contract metadata_and_indexing_intent). Core prints
 * no description; an SEO plugin owns this when one is active, so the fallback steps aside for it.
 */
add_action(
	'wp_head',
	function () {
		if ( defined( 'WPSEO_VERSION' ) || defined( 'RANK_MATH_VERSION' ) || defined( 'AIOSEO_VERSION' ) || defined( 'SEOPRESS_VERSION' ) ) {
			return;
		}
		if ( is_singular() && has_excerpt() ) {
			printf( "<meta name=\"description\" content=\"%s\">\n", esc_attr( wp_strip_all_tags( get_the_excerpt() ) ) );
		} elseif ( is_404() ) {
			printf( "<meta name=\"description\" content=\"%s\">\n", esc_attr__( 'The page you were looking for could not be found.', 'harbour-lane' ) );
		}
	},
	1
);
