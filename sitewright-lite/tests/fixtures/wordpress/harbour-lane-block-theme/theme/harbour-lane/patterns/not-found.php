<?php
/**
 * Title: Page not found
 * Slug: harbour-lane/not-found
 * Categories: text
 * Inserter: no
 * Description: Heading, explanation and links back into the site for the 404 template.
 */
?>
<!-- wp:heading {"level":1} -->
<h1 class="wp-block-heading"><?php esc_html_e( 'Page not found', 'harbour-lane' ); ?></h1>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p><?php esc_html_e( "That page doesn't exist, or it has moved.", 'harbour-lane' ); ?></p>
<!-- /wp:paragraph -->

<!-- wp:list -->
<ul class="wp-block-list"><!-- wp:list-item -->
<li><a href="<?php echo esc_url( home_url( '/' ) ); ?>"><?php esc_html_e( 'Go to the home page', 'harbour-lane' ); ?></a></li>
<!-- /wp:list-item -->

<!-- wp:list-item -->
<li><a href="<?php echo esc_url( home_url( '/menu/' ) ); ?>"><?php esc_html_e( 'See the menu', 'harbour-lane' ); ?></a></li>
<!-- /wp:list-item --></ul>
<!-- /wp:list -->
