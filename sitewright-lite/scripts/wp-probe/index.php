<?php
/**
 * Sitewright read-only WordPress runtime probe.
 *
 * Mount this directory into a disposable local WordPress (for example WordPress Playground:
 * --mount <plugin>/scripts/wp-probe:/wordpress/sw-probe --define SITEWRIGHT_PROBE 1) and request
 * /sw-probe/ from the same machine. It reports versions, the active theme, block templates and parts,
 * theme patterns, and the block structure of published pages as JSON. It writes nothing.
 *
 * Version 2 also identifies the snapshot it observed: a SHA-256 of every file in the active theme
 * directory and of each published page's stored content. sw_wp_theme_check.py accepts runtime
 * results only when that snapshot equals the theme and content it is checking.
 *
 * It refuses to run unless the SITEWRIGHT_PROBE constant is defined and the request comes directly from
 * loopback (no proxy forwarding headers). Never mount it on a live site.
 *
 * Version 3 reports only how many callbacks each watched hook has, not their names.
 */

$sitewright_remote = isset( $_SERVER['REMOTE_ADDR'] ) ? (string) $_SERVER['REMOTE_ADDR'] : '';
// Loopback only. A request relayed by a proxy also arrives from loopback, so forwarded requests are refused too.
$sitewright_forwarded = isset( $_SERVER['HTTP_X_FORWARDED_FOR'] ) || isset( $_SERVER['HTTP_FORWARDED'] ) || isset( $_SERVER['HTTP_X_REAL_IP'] );
if ( $sitewright_forwarded || ! in_array( $sitewright_remote, array( '127.0.0.1', '::1' ), true ) ) {
	http_response_code( 403 );
	exit;
}

require_once dirname( __DIR__ ) . '/wp-load.php';

if ( ! defined( 'SITEWRIGHT_PROBE' ) ) {
	status_header( 404 );
	exit;
}

nocache_headers();
header( 'Content-Type: application/json; charset=utf-8' );

/**
 * Summarise a parsed block tree: block counts by name, freeform (classic) chunks and Custom HTML blocks.
 *
 * @param array $blocks Parsed blocks.
 * @param array $acc    Accumulator.
 * @return array
 */
function sitewright_probe_walk( $blocks, $acc ) {
	foreach ( $blocks as $block ) {
		$name = $block['blockName'];
		if ( null === $name ) {
			if ( '' !== trim( $block['innerHTML'] ) ) {
				$acc['freeform'][] = substr( trim( wp_strip_all_tags( $block['innerHTML'] ) ), 0, 80 );
			}
			continue;
		}
		$acc['counts'][ $name ] = isset( $acc['counts'][ $name ] ) ? $acc['counts'][ $name ] + 1 : 1;
		if ( ! WP_Block_Type_Registry::get_instance()->is_registered( $name ) ) {
			$acc['unregistered'][] = $name;
		}
		if ( ! empty( $block['innerBlocks'] ) ) {
			$acc = sitewright_probe_walk( $block['innerBlocks'], $acc );
		}
	}
	return $acc;
}

/**
 * SHA-256 of every regular file under $dir, keyed by path relative to $dir (sorted), skipping the
 * directories sw_records.py leaves out of fingerprints. Stops after $limit files.
 *
 * @param string $dir   Normalised directory path.
 * @param int    $limit Maximum number of files.
 * @return array array( files, truncated )
 */
function sitewright_probe_files( $dir, $limit ) {
	$files     = array();
	$truncated = false;
	$inner     = new RecursiveDirectoryIterator( $dir, FilesystemIterator::SKIP_DOTS );
	$filter    = new RecursiveCallbackFilterIterator(
		$inner,
		function ( $current ) {
			return ! ( $current->isDir() && in_array( $current->getFilename(), array( '.git', 'node_modules', '__pycache__' ), true ) );
		}
	);
	foreach ( new RecursiveIteratorIterator( $filter ) as $sitewright_f ) {
		if ( $sitewright_f->isLink() || ! $sitewright_f->isFile() ) {
			$rel           = ltrim( substr( wp_normalize_path( $sitewright_f->getPathname() ), strlen( $dir ) ), '/' );
			$files[ $rel ] = 'link';
			continue;
		}
		if ( count( $files ) >= $limit ) {
			$truncated = true;
			break;
		}
		$rel           = ltrim( substr( wp_normalize_path( $sitewright_f->getPathname() ), strlen( $dir ) ), '/' );
		$files[ $rel ] = 'sha256:' . hash_file( 'sha256', $sitewright_f->getPathname() );
	}
	ksort( $files, SORT_STRING );
	return array( $files, $truncated );
}

$sitewright_theme = wp_get_theme();
$sitewright_dir   = untrailingslashit( wp_normalize_path( get_stylesheet_directory() ) );
list( $sitewright_files, $sitewright_truncated ) = sitewright_probe_files( $sitewright_dir, 2000 );
$sitewright_out   = array(
	'probe'        => 'sitewright-wp-probe 3',
	'php_version'  => PHP_VERSION,
	'wp_version'   => get_bloginfo( 'version' ),
	'theme'        => array(
		'stylesheet'     => get_stylesheet(),
		'template'       => get_template(),
		'name'           => $sitewright_theme->get( 'Name' ),
		'version'        => $sitewright_theme->get( 'Version' ),
		'is_block_theme' => wp_is_block_theme(),
		'errors'         => is_wp_error( $sitewright_theme->errors() ) ? $sitewright_theme->errors()->get_error_messages() : array(),
		'files'          => (object) $sitewright_files,
		'files_truncated' => $sitewright_truncated,
	),
	'settings'     => array(
		'show_on_front'       => get_option( 'show_on_front' ),
		'page_on_front'       => (int) get_option( 'page_on_front' ),
		'permalink_structure' => get_option( 'permalink_structure' ),
	),
	'templates'    => array(),
	'parts'        => array(),
	'patterns'     => array(),
	'pages'        => array(),
	'mu_plugins'   => array_map( 'basename', array_keys( get_mu_plugins() ) ),
	'plugins'      => array_values( (array) get_option( 'active_plugins', array() ) ),
	'hooks'        => array(),
);

foreach ( get_block_templates( array(), 'wp_template' ) as $sitewright_t ) {
	$sitewright_out['templates'][] = array( 'slug' => $sitewright_t->slug, 'source' => $sitewright_t->source, 'has_theme_file' => (bool) $sitewright_t->has_theme_file );
}
foreach ( get_block_templates( array(), 'wp_template_part' ) as $sitewright_t ) {
	$sitewright_out['parts'][] = array( 'slug' => $sitewright_t->slug, 'area' => $sitewright_t->area, 'source' => $sitewright_t->source );
}
foreach ( WP_Block_Patterns_Registry::get_instance()->get_all_registered() as $sitewright_p ) {
	$sitewright_file = isset( $sitewright_p['filePath'] ) ? wp_normalize_path( $sitewright_p['filePath'] ) : '';
	if ( '' !== $sitewright_file && 0 === strpos( $sitewright_file, $sitewright_dir . '/' ) ) {
		$sitewright_out['patterns'][] = array( 'slug' => $sitewright_p['name'], 'title' => $sitewright_p['title'] );
	}
}
foreach ( get_posts( array( 'post_type' => 'page', 'post_status' => 'publish', 'numberposts' => 100, 'orderby' => 'menu_order', 'order' => 'ASC' ) ) as $sitewright_page ) {
	$sitewright_walk                = sitewright_probe_walk( parse_blocks( $sitewright_page->post_content ), array( 'counts' => array(), 'freeform' => array(), 'unregistered' => array() ) );
	$sitewright_out['pages'][]      = array(
		'slug'         => $sitewright_page->post_name,
		'path'         => wp_make_link_relative( get_permalink( $sitewright_page ) ),
		'template'     => get_page_template_slug( $sitewright_page ),
		'menu_order'   => (int) $sitewright_page->menu_order,
		'has_blocks'   => has_blocks( $sitewright_page->post_content ),
		'content_sha256' => 'sha256:' . hash( 'sha256', $sitewright_page->post_content ),
		'block_counts' => $sitewright_walk['counts'],
		'freeform'     => $sitewright_walk['freeform'],
		'unregistered' => array_values( array_unique( $sitewright_walk['unregistered'] ) ),
	);
}
foreach ( array( 'template_redirect', 'wp_head' ) as $sitewright_hook ) {
	$sitewright_count = 0;
	if ( isset( $GLOBALS['wp_filter'][ $sitewright_hook ] ) ) {
		foreach ( $GLOBALS['wp_filter'][ $sitewright_hook ]->callbacks as $sitewright_cbs ) {
			$sitewright_count += count( $sitewright_cbs );
		}
	}
	$sitewright_out['hooks'][ $sitewright_hook ] = array( 'callbacks' => $sitewright_count );
}

echo wp_json_encode( $sitewright_out, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES );
